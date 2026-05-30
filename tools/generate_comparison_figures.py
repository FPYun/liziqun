"""
Generate thesis comparison figures from structured JSON results.

Inputs:
  results/algorithm_comparison.json
  results/boundary_analysis.json

Outputs:
  TongjiThesis-1.4.3/figures/algorithm_pareto_overlay.pdf
  TongjiThesis-1.4.3/figures/algorithm_metrics_bars.pdf
  TongjiThesis-1.4.3/figures/runtime_quality_tradeoff.pdf
  TongjiThesis-1.4.3/figures/boundary_coverage_map.pdf
  TongjiThesis-1.4.3/figures/knee_deployment_comparison.pdf
"""

from __future__ import annotations

import json
import os
import sys
import argparse
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from experiments.boundary_analysis import build_boundary_scenario
from experiments.compare_algorithms import build_scenario
from src.benchmarks import find_knee_point
from src.evaluation import calculate_reception_probability, generate_boundary_task_points
from src.metrics import filter_nondominated

RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
FIG_DIR = os.path.join(PROJECT_ROOT, "TongjiThesis-1.4.3", "figures")

METHOD_LABELS = {
    "ours": "MOPSO-DT (ours)",
    "mopso_legacy": "MOPSO-DT legacy",
    "nsga2": "NSGA-II-DT",
    "moead": "MOEA/D-DT",
    "spea2": "SPEA2-DT",
    "random": "Random",
    "ours_transform": "Transform",
    "direct_physical": "Direct",
}

BAR_LABELS = {
    "ours": "Ours",
    "mopso_legacy": "Leg.",
    "nsga2": "NSGA",
    "moead": "MOEA",
    "spea2": "SPEA2",
    "random": "Rand.",
}

COLORS = {
    "ours": "#D55E00",
    "mopso_legacy": "#0072B2",
    "nsga2": "#009E73",
    "moead": "#CC79A7",
    "spea2": "#E69F00",
    "random": "#7F7F7F",
    "ours_transform": "#D55E00",
    "direct_physical": "#0072B2",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "font.family": "serif",
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "mathtext.fontset": "stix",
        }
    )


def load_json(path: str) -> Dict | None:
    if not os.path.exists(path):
        print(f"Skip missing input: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(fig, name: str) -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")


def aggregate_summary_by_scenario(data: Dict, scenario: str) -> List[Dict]:
    return [row for row in data.get("summary", []) if row.get("scenario") == scenario]


def runs_by_scenario(data: Dict, scenario: str) -> List[Dict]:
    return [run for run in data.get("runs", []) if run.get("scenario") == scenario]


def front_curve_from_ecr_jmin(ecr: np.ndarray, jmin: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return a sorted max-max nondominated envelope in physical objective space."""
    if len(ecr) == 0 or len(jmin) == 0:
        return np.asarray([]), np.asarray([])
    objective_view = np.column_stack([1.0 - ecr, -jmin])
    indices = filter_nondominated(objective_view)
    if not indices:
        return np.asarray([]), np.asarray([])
    front_ecr = ecr[indices]
    front_jmin = jmin[indices]
    order = np.argsort(front_ecr)
    return front_ecr[order], front_jmin[order]


def plot_algorithm_pareto_overlay(data: Dict, scenario: str = "challenging") -> None:
    runs = runs_by_scenario(data, scenario)
    if not runs:
        return

    fig, ax = plt.subplots(figsize=(5.4, 3.8))
    methods = sorted({run["method"] for run in runs})
    for method in methods:
        method_runs = [run for run in runs if run["method"] == method]
        ecr = np.concatenate([np.asarray(run["ecr_values"], dtype=float) for run in method_runs])
        jmin = np.concatenate([np.asarray(run["jmin_values"], dtype=float) for run in method_runs])
        front_ecr, front_jmin = front_curve_from_ecr_jmin(ecr, jmin)
        if len(front_ecr) >= 2:
            ax.plot(
                front_ecr,
                front_jmin,
                color=COLORS.get(method),
                linewidth=1.35,
                alpha=0.88,
                zorder=2,
            )
        ax.scatter(
            ecr,
            jmin,
            s=24,
            alpha=0.75,
            color=COLORS.get(method),
            label=METHOD_LABELS.get(method, method),
            edgecolors="white",
            linewidth=0.3,
            zorder=3,
        )
    ax.set_xlabel("ECR")
    ax.set_ylabel(r"$J_{\min}$ (W/m$^2$)")
    ax.grid(alpha=0.18)
    ax.legend(frameon=False, ncol=2)
    save(fig, "algorithm_pareto_overlay.pdf")


def plot_algorithm_metrics_bars(data: Dict, scenario: str = "challenging") -> None:
    rows = aggregate_summary_by_scenario(data, scenario)
    if not rows:
        return

    order = ["ours", "mopso_legacy", "nsga2", "moead", "spea2", "random"]
    rows_by_method = {row["method"]: row for row in rows}
    methods = [method for method in order if method in rows_by_method]
    metrics = [
        ("hv", "HV", True),
        ("spacing", "Spacing", False),
        ("n_solutions", "Solutions", True),
        ("runtime", "Runtime (s)", False),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.2))
    axes = axes.flatten()
    x = np.arange(len(methods))
    tick_labels = [BAR_LABELS.get(m, METHOD_LABELS.get(m, m).replace("-DT", "")) for m in methods]
    for ax, (metric, label, higher_better) in zip(axes, metrics):
        means = [rows_by_method[m].get(f"{metric}_mean", 0.0) for m in methods]
        stds = [rows_by_method[m].get(f"{metric}_std", 0.0) for m in methods]
        colors = [COLORS.get(m, "#999999") for m in methods]
        ax.bar(x, means, yerr=stds, capsize=2.5, color=colors, alpha=0.88)
        ax.set_ylabel(label)
        ax.set_xticks(x)
        ax.set_xticklabels(tick_labels, rotation=0, ha="center")
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.18)
        if means:
            best_idx = int(np.argmax(means) if higher_better else np.argmin(means))
            ax.patches[best_idx].set_edgecolor("black")
            ax.patches[best_idx].set_linewidth(1.2)
    fig.subplots_adjust(hspace=0.48, wspace=0.28, bottom=0.12)
    save(fig, "algorithm_metrics_bars.pdf")


def plot_runtime_quality_tradeoff(data: Dict, scenario: str = "challenging") -> None:
    rows = aggregate_summary_by_scenario(data, scenario)
    if not rows:
        return

    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    runtimes = [row.get("runtime_mean", 0.0) for row in rows]
    hvs = [row.get("hv_mean", 0.0) for row in rows]
    for row in rows:
        method = row["method"]
        runtime = row.get("runtime_mean", 0.0)
        hv = row.get("hv_mean", 0.0)
        n_solutions = row.get("n_solutions_mean", 1.0)
        ax.scatter(
            runtime,
            hv,
            s=max(45.0, n_solutions * 9.0),
            color=COLORS.get(method),
            alpha=0.78,
            edgecolors="black" if method == "ours" else "white",
            linewidth=0.8,
        )
        ax.annotate(METHOD_LABELS.get(method, method), (runtime, hv), xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Runtime (s)")
    ax.set_ylabel("HV")
    runtime_span = max(runtimes) - min(runtimes)
    hv_span = max(hvs) - min(hvs)
    runtime_pad = max(4.0, runtime_span * 0.55)
    hv_pad = max(0.0012, hv_span * 0.45)
    ax.set_xlim(min(runtimes) - runtime_pad, max(runtimes) + runtime_pad)
    ax.set_ylim(max(0.0, min(hvs) - hv_pad), max(hvs) + hv_pad)
    ax.grid(alpha=0.18)
    save(fig, "runtime_quality_tradeoff.pdf")


def boundary_coverage_mask(positions: np.ndarray, boundary_points, radar_configs) -> np.ndarray:
    covered = []
    threshold = radar_configs[0].P_min
    for point in boundary_points:
        miss_prob = 1.0
        for radar_pos, config in zip(positions, radar_configs):
            p = calculate_reception_probability((radar_pos[0], radar_pos[1]), (point.x, point.y), config)
            miss_prob *= 1.0 - p
        covered.append(1.0 - miss_prob >= threshold)
    return np.asarray(covered, dtype=bool)


def plot_boundary_coverage_map(data: Dict) -> None:
    runs = data.get("runs", [])
    if not runs:
        return
    scenario = build_boundary_scenario()
    boundary_points = generate_boundary_task_points(scenario.region, grid_size=25)
    selected = []
    for method in ["ours_transform", "direct_physical"]:
        candidates = [run for run in runs if run["method"] == method]
        if candidates:
            selected.append(max(candidates, key=lambda run: run.get("boundary_ecr", 0.0)))
    if not selected:
        return

    fig, axes = plt.subplots(1, len(selected), figsize=(4.0 * len(selected), 3.8), sharex=True, sharey=True)
    if len(selected) == 1:
        axes = [axes]
    bx = np.array([p.x for p in boundary_points])
    by = np.array([p.y for p in boundary_points])
    for ax, run in zip(axes, selected):
        idx = run["best_boundary_index"]
        positions = np.asarray(run["positions"][idx], dtype=float)
        covered = boundary_coverage_mask(positions, boundary_points, scenario.radar_configs)
        x, y = scenario.region.exterior.xy
        ax.plot(x, y, color="black", linewidth=1.0)
        ax.scatter(bx[~covered], by[~covered], s=10, color="#D55E00", alpha=0.75, label="uncovered")
        ax.scatter(bx[covered], by[covered], s=10, color="#009E73", alpha=0.75, label="covered")
        ax.scatter(positions[:, 0], positions[:, 1], marker="^", s=42, color="#0072B2", edgecolors="white", linewidth=0.4)
        ax.set_aspect("equal")
        ax.set_xlabel("x (km)")
        ax.set_ylabel("y (km)")
        ax.text(
            0.02,
            0.98,
            f"{METHOD_LABELS.get(run['method'], run['method'])}\nBoundary ECR={run['boundary_ecr']:.2f}",
            transform=ax.transAxes,
            va="top",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82),
        )
    axes[0].legend(frameon=False, loc="lower left")
    save(fig, "boundary_coverage_map.pdf")


def plot_knee_deployment_comparison(data: Dict, scenario_name: str = "challenging") -> None:
    runs = runs_by_scenario(data, scenario_name)
    if not runs:
        return
    scenario = build_scenario(scenario_name)
    summary = aggregate_summary_by_scenario(data, scenario_name)
    baseline_rows = [row for row in summary if row["method"] != "ours"]
    if not baseline_rows:
        return
    best_baseline = max(baseline_rows, key=lambda row: row.get("hv_mean", 0.0))["method"]
    selected = []
    for method in ["ours", best_baseline]:
        method_runs = [run for run in runs if run["method"] == method]
        if method_runs:
            selected.append(max(method_runs, key=lambda run: run.get("hv", 0.0)))
    if len(selected) < 2:
        return

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.5), sharex=True, sharey=True)
    for ax, run in zip(axes, selected):
        objectives = np.asarray([entry["objectives"] for entry in run["archive"]], dtype=float)
        if len(objectives) == 0:
            continue
        knee_idx = int(find_knee_point(objectives)) if len(objectives) >= 3 else 0
        positions = np.asarray(run["positions"][knee_idx], dtype=float)
        for poly in scenario.polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, facecolor="#EAF2F8", edgecolor="#5D6D7E", linewidth=0.7, alpha=0.8)
        task_x = [point.x for point in scenario.task_points]
        task_y = [point.y for point in scenario.task_points]
        ax.scatter(task_x, task_y, s=4, color="#AAAAAA", alpha=0.35)
        ax.scatter(positions[:, 0], positions[:, 1], marker="^", s=56, color=COLORS.get(run["method"]), edgecolors="white", linewidth=0.5)
        ax.set_aspect("equal")
        ax.set_xlabel("x (km)")
        ax.set_ylabel("y (km)")
        ax.text(
            0.02,
            0.98,
            f"{METHOD_LABELS.get(run['method'], run['method'])}\nHV={run['hv']:.3f}",
            transform=ax.transAxes,
            va="top",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82),
        )
    save(fig, "knee_deployment_comparison.pdf")


def main() -> None:
    global RESULTS_DIR, FIG_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=RESULTS_DIR)
    parser.add_argument("--figure-dir", default=FIG_DIR)
    args = parser.parse_args()
    RESULTS_DIR = args.results_dir
    FIG_DIR = args.figure_dir

    configure_style()
    algorithm_data = load_json(os.path.join(RESULTS_DIR, "algorithm_comparison.json"))
    boundary_data = load_json(os.path.join(RESULTS_DIR, "boundary_analysis.json"))

    if algorithm_data is not None:
        plot_algorithm_pareto_overlay(algorithm_data)
        plot_algorithm_metrics_bars(algorithm_data)
        plot_runtime_quality_tradeoff(algorithm_data)
        plot_knee_deployment_comparison(algorithm_data)

    if boundary_data is not None:
        plot_boundary_coverage_map(boundary_data)


if __name__ == "__main__":
    main()
