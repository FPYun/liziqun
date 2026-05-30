"""
Boundary-effect analysis for coordinate-transform deployment search.

Outputs:
  results/boundary_analysis.json

Example:
  python experiments/boundary_analysis.py --seeds 2026 --T_max 5 --N_P 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from typing import Dict, List

import numpy as np
from shapely.geometry import Point, Polygon as ShapelyPolygon

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from experiments.compare_algorithms import MOPSOFairBudget, Scenario, expected_evaluation_budget
from src.baseline_algorithms import NSGA2_DT
from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig,
    calculate_boundary_ecr,
    calculate_ecr,
    calculate_jamming_density,
    create_normalized_evaluate_function,
    decode_particle,
    generate_boundary_task_points,
    generate_uniform_task_points,
)
from src.metrics import calculate_archive_metrics, to_serializable_archive
from src.mopso import MOPSO_DT


def build_boundary_scenario() -> Scenario:
    region = ShapelyPolygon([(0, 0), (200, 0), (200, 80), (80, 80), (80, 200), (0, 200)])
    J = 8
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    task_points = generate_uniform_task_points(region, grid_size=15)
    radar_configs = [
        RadarConfig(
            P0=0.9,
            P_min=0.8,
            beta=0.03,
            alpha_air=2.0,
            alpha_ground=4.0,
            jammer_P_t=150.0,
            jammer_G_t_dB=30.0,
        )
        for _ in range(J)
    ]
    J_max_ref = 0.005
    evaluate_func = create_normalized_evaluate_function(
        task_points,
        radar_configs,
        polygons,
        J,
        N_bin,
        J_max_ref=J_max_ref,
    )
    return Scenario(
        name="boundary_l_shape",
        region=region,
        polygons=polygons,
        task_points=task_points,
        radar_configs=radar_configs,
        J=J,
        N_bin=N_bin,
        J_max_ref=J_max_ref,
        evaluate_func=evaluate_func,
        metadata={"region_km": "L-shape within 200x200", "model": "exponential", "beta": 0.03},
    )


def direct_positions_from_continuous(continuous: np.ndarray, scenario: Scenario) -> np.ndarray:
    minx, miny, maxx, maxy = scenario.region.bounds
    positions = []
    for j in range(scenario.J):
        x = minx + continuous[2 * j] * (maxx - minx)
        y = miny + continuous[2 * j + 1] * (maxy - miny)
        point = Point(x, y)
        if not scenario.region.contains(point):
            nearest = scenario.region.exterior.interpolate(scenario.region.exterior.project(point))
            x, y = nearest.x, nearest.y
        positions.append((x, y))
    return np.asarray(positions, dtype=float)


def make_direct_evaluate_func(scenario: Scenario):
    def evaluate(Phi):
        continuous = Phi[:, :2].flatten()
        positions = direct_positions_from_continuous(continuous, scenario)
        ecr = calculate_ecr(positions, scenario.task_points, scenario.radar_configs)
        jmin = calculate_jamming_density(positions, scenario.task_points, scenario.radar_configs)
        return np.array([1.0 - ecr, scenario.J_max_ref / (jmin + scenario.J_max_ref + 1e-10)])

    return evaluate


class DirectPhysicalMOPSO:
    def __init__(self, scenario: Scenario, N_P: int, T_max: int, seed: int):
        self.scenario = scenario
        self.N_P = N_P
        self.T_max = T_max
        self.seed = seed

    def optimize(self):
        if self.T_max < 2:
            raise ValueError("DirectPhysicalMOPSO requires T_max >= 2")
        np.random.seed(self.seed)
        optimizer = MOPSO_DT(
            J=self.scenario.J,
            N_bin=self.scenario.N_bin,
            evaluate_func=make_direct_evaluate_func(self.scenario),
            N_P=self.N_P,
            T_max=self.T_max - 1,
            c_1=2.0,
            c_2=2.0,
            p_c=0.9,
            archive_size=100,
            verbose=False,
            w_strategy="standard",
            p_m_base=0.01,
            select_gb="crowding",
        )
        import time

        start = time.time()
        archive, stats = optimizer.optimize()
        elapsed = time.time() - start
        stats = dict(stats)
        stats.update(
            {
                "method": "direct_physical",
                "seed": self.seed,
                "evaluations": expected_evaluation_budget(self.N_P, self.T_max),
                "runtime": float(elapsed),
                "archive_size": len(archive),
            }
        )
        return archive, stats


def method_optimizer(method: str, scenario: Scenario, N_P: int, T_max: int, seed: int):
    if method == "ours_transform":
        return MOPSOFairBudget(
            scenario=scenario,
            method_name="ours_transform",
            N_P=N_P,
            T_max=T_max,
            seed=seed,
            w_strategy="standard",
            p_m_base=0.01,
            select_gb="crowding",
        )
    if method == "direct_physical":
        return DirectPhysicalMOPSO(scenario, N_P=N_P, T_max=T_max, seed=seed)
    if method == "mopso_legacy":
        return MOPSOFairBudget(
            scenario=scenario,
            method_name="mopso_legacy",
            N_P=N_P,
            T_max=T_max,
            seed=seed,
            w_strategy="legacy",
            p_m_base=0.0,
            select_gb="random",
        )
    if method == "nsga2":
        return NSGA2_DT(scenario.J, scenario.N_bin, scenario.evaluate_func, N_P=N_P, T_max=T_max, seed=seed)
    raise ValueError(f"Unknown method: {method}")


def decode_positions(entry: Dict, scenario: Scenario, method: str) -> np.ndarray:
    continuous = np.asarray(entry["continuous"], dtype=float)
    binary = np.asarray(entry["binary"], dtype=int)
    if method == "direct_physical":
        return direct_positions_from_continuous(continuous, scenario)
    return np.asarray(decode_particle(continuous, binary, scenario.J, scenario.N_bin, scenario.polygons), dtype=float)


def analyze_archive(archive: List[Dict], scenario: Scenario, method: str, boundary_points: list) -> Dict:
    overall_values = []
    boundary_values = []
    jmin_values = []
    positions = []
    for entry in archive:
        pa = decode_positions(entry, scenario, method)
        continuous = np.asarray(entry["continuous"], dtype=float)
        binary = np.asarray(entry["binary"], dtype=int)
        if method == "direct_physical":
            overall = calculate_ecr(pa, scenario.task_points, scenario.radar_configs)
            boundary = calculate_boundary_ecr(pa, boundary_points, scenario.radar_configs)
            jmin = calculate_jamming_density(pa, scenario.task_points, scenario.radar_configs)
        else:
            overall = calculate_ecr(
                pa,
                scenario.task_points,
                scenario.radar_configs,
                convex_polygons=scenario.polygons,
                binary_codes=binary,
                continuous_coords=continuous.reshape(scenario.J, 2),
            )
            boundary = calculate_boundary_ecr(
                pa,
                boundary_points,
                scenario.radar_configs,
                convex_polygons=scenario.polygons,
                binary_codes=binary,
                continuous_coords=continuous.reshape(scenario.J, 2),
            )
            jmin = calculate_jamming_density(
                pa,
                scenario.task_points,
                scenario.radar_configs,
                convex_polygons=scenario.polygons,
                binary_codes=binary,
                continuous_coords=continuous.reshape(scenario.J, 2),
            )
        overall_values.append(float(overall))
        boundary_values.append(float(boundary))
        jmin_values.append(float(jmin))
        positions.append(pa.tolist())

    if not boundary_values:
        return {
            "overall_ecr": 0.0,
            "boundary_ecr": 0.0,
            "boundary_gap": 0.0,
            "jmin": 0.0,
            "best_boundary_index": -1,
            "positions": [],
        }

    best_idx = int(np.argmax(boundary_values))
    overall = overall_values[best_idx]
    boundary = boundary_values[best_idx]
    return {
        "overall_ecr": float(overall),
        "boundary_ecr": float(boundary),
        "boundary_gap": float(overall - boundary),
        "jmin": float(jmin_values[best_idx]),
        "best_boundary_index": best_idx,
        "overall_ecr_values": overall_values,
        "boundary_ecr_values": boundary_values,
        "jmin_values": jmin_values,
        "positions": positions,
    }


def run_method(method: str, scenario: Scenario, seed: int, N_P: int, T_max: int, boundary_points: list) -> Dict:
    optimizer = method_optimizer(method, scenario, N_P, T_max, seed)
    archive, stats = optimizer.optimize()
    for entry in archive:
        entry["scenario"] = scenario.name
        entry["method"] = method
        entry["seed"] = int(seed)
    quality = calculate_archive_metrics(archive, ref_point=(1.1, 1.1))
    boundary = analyze_archive(archive, scenario, method, boundary_points)
    return {
        "scenario": scenario.name,
        "method": method,
        "seed": int(seed),
        "N_P": int(N_P),
        "T_max": int(T_max),
        "boundary_task_points": len(boundary_points),
        **stats,
        **quality,
        **boundary,
        "archive": to_serializable_archive(archive),
    }


def build_summary(runs: List[Dict]) -> List[Dict]:
    from src.metrics import summarize_metric_records

    return summarize_metric_records(
        runs,
        metric_names=["overall_ecr", "boundary_ecr", "boundary_gap", "jmin", "hv", "spacing", "runtime"],
    )


def save_results(path: str, runs: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "metadata": {
            "description": "Boundary ECR analysis on an L-shaped complex region",
            "selection_rule": "report solution with maximum boundary ECR in each archive",
        },
        "runs": runs,
        "summary": build_summary(runs),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", nargs="+", default=["ours_transform", "direct_physical", "mopso_legacy", "nsga2"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[2026, 2027, 2028])
    parser.add_argument("--N_P", type=int, default=50)
    parser.add_argument("--T_max", type=int, default=80)
    parser.add_argument("--boundary_grid", type=int, default=25)
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "results", "boundary_analysis.json"))
    args = parser.parse_args()

    scenario = build_boundary_scenario()
    boundary_points = generate_boundary_task_points(scenario.region, grid_size=args.boundary_grid)
    runs = []
    print(f"# Boundary scenario: {scenario.name} | boundary points={len(boundary_points)}")
    for seed in args.seeds:
        for method in args.methods:
            print(f"Running {method} seed={seed} ...", flush=True)
            record = run_method(method, scenario, seed, args.N_P, args.T_max, boundary_points)
            print(
                f"  boundary_ECR={record['boundary_ecr']:.3f} overall_ECR={record['overall_ecr']:.3f} "
                f"gap={record['boundary_gap']:.3f} HV={record['hv']:.4f} time={record['runtime']:.1f}s"
            )
            runs.append(record)
            save_results(args.output, runs)
    print(f"Saved: {os.path.relpath(args.output, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
