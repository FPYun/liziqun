"""
Fair same-scenario algorithm comparison for the thesis.

Outputs:
  results/algorithm_comparison.json

Example:
  python experiments/compare_algorithms.py --scenario challenging --methods ours random --seeds 2026 --T_max 5 --N_P 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List

import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from src.baseline_algorithms import MOEAD_DT, NSGA2_DT, RandomSearchMO, SPEA2_DT
from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig,
    calculate_ecr,
    calculate_jamming_density,
    create_normalized_evaluate_function,
    decode_particle,
    generate_uniform_task_points,
)
from src.metrics import calculate_archive_metrics, to_serializable_archive
from src.mopso import MOPSO_DT


@dataclass
class Scenario:
    name: str
    region: ShapelyPolygon
    polygons: list
    task_points: list
    radar_configs: list
    J: int
    N_bin: int
    J_max_ref: float
    evaluate_func: Callable[[np.ndarray], np.ndarray]
    metadata: Dict


def create_paper_radar_configs(n_radars: int = 8) -> List[RadarConfig]:
    configs = []
    for _ in range(n_radars):
        configs.append(
            RadarConfig(
                P_t=3000.0,
                G_t_dB=50.0,
                wavelength=0.3,
                sigma=0.1,
                bandwidth=15e6,
                D0_dB=12.5,
                P_fa=1e-6,
                R_max=60.0,
                jammer_P_t=150.0,
                jammer_G_t_dB=30.0,
                use_radar_equation=True,
                P_min=0.5,
                is_air=False,
            )
        )
    return configs


def build_scenario(name: str) -> Scenario:
    decomposer = DeploymentRegionDecomposer(verbose=False)

    if name == "challenging":
        region = ShapelyPolygon([(0, 0), (200, 0), (200, 200), (0, 200)])
        J = 8
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
        metadata = {
            "region_km": "200x200",
            "model": "exponential",
            "beta": 0.03,
            "grid": "15x15",
        }
    elif name == "paper_aligned":
        region = ShapelyPolygon([(0, 0), (300, 0), (300, 300), (0, 300)])
        J = 8
        task_points = generate_uniform_task_points(region, grid_size=10)
        radar_configs = create_paper_radar_configs(J)
        d_test = 300.0
        jammer_gain = 10 ** (radar_configs[0].jammer_G_t_dB / 10.0)
        J_est = radar_configs[0].jammer_P_t * jammer_gain / (4 * np.pi * (d_test * 1000) ** 2)
        J_max_ref = float(J_est * 2)
        metadata = {
            "region_km": "300x300",
            "model": "radar_equation",
            "grid": "10x10",
        }
    else:
        raise ValueError(f"Unknown scenario: {name}")

    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    evaluate_func = create_normalized_evaluate_function(
        task_points,
        radar_configs,
        polygons,
        J,
        N_bin,
        J_max_ref=J_max_ref,
    )
    return Scenario(
        name=name,
        region=region,
        polygons=polygons,
        task_points=task_points,
        radar_configs=radar_configs,
        J=J,
        N_bin=N_bin,
        J_max_ref=J_max_ref,
        evaluate_func=evaluate_func,
        metadata=metadata,
    )


def expected_evaluation_budget(N_P: int, T_max: int) -> int:
    return int(N_P * T_max)


class MOPSOFairBudget:
    """MOPSO-DT wrapper that counts initialization as one evaluation generation."""

    def __init__(
        self,
        scenario: Scenario,
        method_name: str,
        N_P: int,
        T_max: int,
        seed: int,
        w_strategy: str,
        p_m_base: float,
        select_gb: str,
    ):
        self.scenario = scenario
        self.method_name = method_name
        self.N_P = N_P
        self.T_max = T_max
        self.seed = seed
        self.w_strategy = w_strategy
        self.p_m_base = p_m_base
        self.select_gb = select_gb

    def optimize(self):
        if self.T_max < 2:
            raise ValueError("MOPSOFairBudget requires T_max >= 2")
        np.random.seed(self.seed)
        internal_iterations = self.T_max - 1
        optimizer = MOPSO_DT(
            J=self.scenario.J,
            N_bin=self.scenario.N_bin,
            evaluate_func=self.scenario.evaluate_func,
            N_P=self.N_P,
            T_max=internal_iterations,
            c_1=2.0,
            c_2=2.0,
            p_c=0.9,
            archive_size=100,
            verbose=False,
            w_strategy=self.w_strategy,
            p_m_base=self.p_m_base,
            select_gb=self.select_gb,
        )

        start = time.time()
        archive, stats = optimizer.optimize()
        elapsed = time.time() - start
        stats = dict(stats)
        stats.update(
            {
                "method": self.method_name,
                "seed": self.seed,
                "evaluations": expected_evaluation_budget(self.N_P, self.T_max),
                "runtime": float(elapsed),
                "archive_size": len(archive),
                "internal_iterations": internal_iterations,
            }
        )
        return archive, stats


def _ours_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
    return MOPSOFairBudget(
        scenario=scenario,
        method_name="ours",
        N_P=N_P,
        T_max=T_max,
        seed=seed,
        w_strategy="standard",
        p_m_base=0.01,
        select_gb="crowding",
    )


def _legacy_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
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


def _random_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
    return RandomSearchMO(scenario.J, scenario.N_bin, scenario.evaluate_func, N_P=N_P, T_max=T_max, seed=seed)


def _nsga2_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
    return NSGA2_DT(scenario.J, scenario.N_bin, scenario.evaluate_func, N_P=N_P, T_max=T_max, seed=seed)


def _moead_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
    return MOEAD_DT(scenario.J, scenario.N_bin, scenario.evaluate_func, N_P=N_P, T_max=T_max, seed=seed)


def _spea2_factory(scenario: Scenario, N_P: int, T_max: int, seed: int):
    return SPEA2_DT(scenario.J, scenario.N_bin, scenario.evaluate_func, N_P=N_P, T_max=T_max, seed=seed)


METHOD_FACTORIES = {
    "ours": _ours_factory,
    "mopso_legacy": _legacy_factory,
    "nsga2": _nsga2_factory,
    "moead": _moead_factory,
    "spea2": _spea2_factory,
    "random": _random_factory,
}


def enrich_archive(archive: List[Dict], scenario: Scenario, method: str, seed: int) -> List[Dict]:
    enriched = []
    for entry in archive:
        item = dict(entry)
        item["scenario"] = scenario.name
        item["method"] = method
        item["seed"] = int(seed)
        enriched.append(item)
    return enriched


def evaluate_physics(archive: List[Dict], scenario: Scenario) -> Dict:
    ecr_values = []
    jmin_values = []
    positions_list = []
    for entry in archive:
        continuous = np.asarray(entry["continuous"], dtype=float)
        binary = np.asarray(entry["binary"], dtype=int)
        positions = decode_particle(continuous, binary, scenario.J, scenario.N_bin, scenario.polygons)
        positions_array = np.asarray(positions, dtype=float)
        ecr = calculate_ecr(
            positions_array,
            scenario.task_points,
            scenario.radar_configs,
            convex_polygons=scenario.polygons,
            binary_codes=binary,
            continuous_coords=continuous.reshape(scenario.J, 2),
        )
        jmin = calculate_jamming_density(
            positions_array,
            scenario.task_points,
            scenario.radar_configs,
            convex_polygons=scenario.polygons,
            binary_codes=binary,
            continuous_coords=continuous.reshape(scenario.J, 2),
        )
        ecr_values.append(float(ecr))
        jmin_values.append(float(jmin))
        positions_list.append(positions_array.tolist())

    ecr_arr = np.asarray(ecr_values, dtype=float)
    jmin_arr = np.asarray(jmin_values, dtype=float)
    corr = float(np.corrcoef(ecr_arr, jmin_arr)[0, 1]) if len(ecr_arr) > 2 else 0.0
    return {
        "ecr_values": ecr_values,
        "jmin_values": jmin_values,
        "positions": positions_list,
        "ecr_min": float(np.min(ecr_arr)) if len(ecr_arr) else 0.0,
        "ecr_max": float(np.max(ecr_arr)) if len(ecr_arr) else 0.0,
        "jmin_min": float(np.min(jmin_arr)) if len(jmin_arr) else 0.0,
        "jmin_max": float(np.max(jmin_arr)) if len(jmin_arr) else 0.0,
        "ecr_jmin_corr": corr,
    }


def run_method(scenario: Scenario, method: str, seed: int, N_P: int, T_max: int) -> Dict:
    optimizer = METHOD_FACTORIES[method](scenario=scenario, N_P=N_P, T_max=T_max, seed=seed)
    archive, stats = optimizer.optimize()
    enriched = enrich_archive(archive, scenario, method, seed)
    quality = calculate_archive_metrics(enriched, ref_point=(1.1, 1.1))
    physics = evaluate_physics(enriched, scenario)
    record = {
        "scenario": scenario.name,
        "method": method,
        "seed": int(seed),
        "N_P": int(N_P),
        "T_max": int(T_max),
        "expected_evaluations": expected_evaluation_budget(N_P, T_max),
        **stats,
        **quality,
        **physics,
        "archive": to_serializable_archive(enriched),
    }
    return record


def load_existing_results(path: str) -> Dict:
    if not os.path.exists(path):
        return {"runs": [], "summary": [], "metadata": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_summary(runs: List[Dict]) -> List[Dict]:
    from src.metrics import summarize_metric_records

    return summarize_metric_records(
        runs,
        metric_names=[
            "hv",
            "spacing",
            "n_solutions",
            "runtime",
            "ecr_max",
            "jmin_max",
            "ecr_jmin_corr",
        ],
    )


def save_results(path: str, runs: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "metadata": {
            "description": "Same-scenario multi-objective optimizer comparison",
            "objective_protocol": "minimize f1=1-ECR and f2=J_ref/(J_min+J_ref)",
            "methods": list(METHOD_FACTORIES.keys()),
        },
        "runs": runs,
        "summary": build_summary(runs),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["challenging", "paper_aligned"], default="challenging")
    parser.add_argument("--methods", nargs="+", default=list(METHOD_FACTORIES.keys()), choices=list(METHOD_FACTORIES.keys()))
    parser.add_argument("--seeds", nargs="+", type=int, default=[2026, 2027, 2028])
    parser.add_argument("--N_P", type=int, default=50)
    parser.add_argument("--T_max", type=int, default=80)
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "results", "algorithm_comparison.json"))
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    scenario = build_scenario(args.scenario)
    existing = load_existing_results(args.output) if args.append else {"runs": []}
    runs = list(existing.get("runs", []))

    print(f"# Scenario: {scenario.name} | N_P={args.N_P} | T_max={args.T_max}")
    for seed in args.seeds:
        for method in args.methods:
            print(f"Running {method} seed={seed} ...", flush=True)
            record = run_method(scenario, method, seed, args.N_P, args.T_max)
            print(
                f"  HV={record['hv']:.4f} Spacing={record['spacing']:.4f} "
                f"Sols={record['n_solutions']} ECR=[{record['ecr_min']:.3f},{record['ecr_max']:.3f}] "
                f"Time={record['runtime']:.1f}s"
            )
            runs.append(record)
            save_results(args.output, runs)

    print(f"Saved: {os.path.relpath(args.output, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
