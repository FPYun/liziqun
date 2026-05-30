"""
Unified metrics and archive helpers for multi-objective radar deployment.

All objective vectors are treated as minimization objectives:
f1 = 1 - ECR, f2 = normalized jamming loss.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from .optimization_utils import calculate_crowding_distance, dominates


def filter_nondominated(objectives: np.ndarray) -> List[int]:
    """Return indices of nondominated rows in deterministic objective order."""
    objectives = np.asarray(objectives, dtype=float)
    if objectives.size == 0:
        return []
    if objectives.ndim != 2:
        raise ValueError("objectives must be a 2D array")

    keep = []
    for i in range(len(objectives)):
        is_dominated = False
        for j in range(len(objectives)):
            if i == j:
                continue
            if dominates(objectives[j], objectives[i]):
                is_dominated = True
                break
        if not is_dominated:
            keep.append(i)

    keep.sort(key=lambda idx: tuple(objectives[idx]))
    return keep


def calculate_hypervolume_2d(
    objectives: np.ndarray,
    ref_point: Sequence[float] = (1.1, 1.1),
) -> float:
    """Calculate exact dominated hypervolume for a 2D minimization front."""
    objectives = np.asarray(objectives, dtype=float)
    ref = np.asarray(ref_point, dtype=float)
    if objectives.size == 0:
        return 0.0
    if objectives.ndim != 2 or objectives.shape[1] != 2:
        raise ValueError("objectives must have shape (n, 2)")
    if ref.shape != (2,):
        raise ValueError("ref_point must contain exactly two values")

    nondom = objectives[filter_nondominated(objectives)]
    valid = nondom[(nondom[:, 0] < ref[0]) & (nondom[:, 1] < ref[1])]
    if len(valid) == 0:
        return 0.0

    sorted_obj = valid[np.argsort(valid[:, 0])]
    hv = 0.0
    best_f2 = ref[1]
    for f1, f2 in sorted_obj:
        if f2 < best_f2:
            hv += max(ref[0] - f1, 0.0) * max(best_f2 - f2, 0.0)
            best_f2 = f2
    return float(hv)


def calculate_spacing(objectives: np.ndarray) -> float:
    """Calculate the spacing metric using nearest-neighbor L1 distances."""
    objectives = np.asarray(objectives, dtype=float)
    if len(objectives) <= 2:
        return 0.0

    distances = []
    for i in range(len(objectives)):
        nearest = np.inf
        for j in range(len(objectives)):
            if i == j:
                continue
            nearest = min(nearest, float(np.sum(np.abs(objectives[i] - objectives[j]))))
        distances.append(nearest)

    distances_arr = np.asarray(distances)
    mean_distance = float(np.mean(distances_arr))
    return float(np.sqrt(np.sum((distances_arr - mean_distance) ** 2) / (len(objectives) - 1)))


def truncate_by_crowding(archive: List[Dict], archive_size: int) -> List[Dict]:
    """Keep the most diverse archive entries according to crowding distance."""
    if len(archive) <= archive_size:
        return archive
    objectives = np.array([entry["objectives"] for entry in archive], dtype=float)
    distances = calculate_crowding_distance(objectives)
    finite = distances[np.isfinite(distances)]
    finite_max = float(np.max(finite)) if len(finite) else 1.0
    distances = np.where(np.isfinite(distances), distances, finite_max * 10.0)
    order = np.argsort(distances)[::-1]
    return [archive[i] for i in order[:archive_size]]


def update_archive(
    archive: List[Dict],
    candidates: Iterable[Dict],
    archive_size: int = 100,
) -> List[Dict]:
    """Merge candidates into an archive, retain nondominated diverse entries."""
    merged = [deepcopy(entry) for entry in archive]
    merged.extend(deepcopy(entry) for entry in candidates)
    if not merged:
        return []

    objectives = np.array([entry["objectives"] for entry in merged], dtype=float)
    indices = filter_nondominated(objectives)
    nondominated = [merged[i] for i in indices]
    nondominated = truncate_by_crowding(nondominated, archive_size)
    nondominated.sort(key=lambda entry: tuple(np.asarray(entry["objectives"], dtype=float)))
    return nondominated


def archive_objectives(archive: List[Dict]) -> np.ndarray:
    """Extract objective matrix from an archive."""
    if not archive:
        return np.empty((0, 2))
    return np.array([entry["objectives"] for entry in archive], dtype=float)


def calculate_archive_metrics(
    archive: List[Dict],
    ref_point: Sequence[float] = (1.1, 1.1),
) -> Dict[str, float]:
    """Summarize objective-space quality for one archive."""
    objectives = archive_objectives(archive)
    return {
        "n_solutions": int(len(objectives)),
        "hv": calculate_hypervolume_2d(objectives, ref_point=ref_point),
        "spacing": calculate_spacing(objectives),
    }


def summarize_metric_records(
    records: List[Dict],
    metric_names: Sequence[str],
    group_keys: Sequence[str] = ("scenario", "method"),
) -> List[Dict]:
    """Group records and compute mean/std for selected metric names."""
    groups: Dict[Tuple, List[Dict]] = defaultdict(list)
    for record in records:
        key = tuple(record.get(group_key) for group_key in group_keys)
        groups[key].append(record)

    summary = []
    for key, items in sorted(groups.items()):
        row = {group_key: value for group_key, value in zip(group_keys, key)}
        row["n"] = len(items)
        for metric_name in metric_names:
            values = np.array([item[metric_name] for item in items if metric_name in item], dtype=float)
            if len(values) == 0:
                continue
            row[f"{metric_name}_mean"] = float(np.mean(values))
            row[f"{metric_name}_std"] = float(np.std(values, ddof=0))
        summary.append(row)
    return summary


def to_serializable_archive(archive: List[Dict]) -> List[Dict]:
    """Convert numpy arrays in archive entries to JSON-serializable lists."""
    serializable = []
    for entry in archive:
        serializable.append(
            {
                **{k: v for k, v in entry.items() if k not in {"continuous", "binary", "objectives"}},
                "continuous": np.asarray(entry["continuous"], dtype=float).tolist(),
                "binary": np.asarray(entry["binary"], dtype=int).tolist(),
                "objectives": np.asarray(entry["objectives"], dtype=float).tolist(),
            }
        )
    return serializable


def from_serializable_archive(entries: List[Dict]) -> List[Dict]:
    """Restore archive arrays from JSON data."""
    archive = []
    for entry in entries:
        restored = dict(entry)
        restored["continuous"] = np.asarray(entry["continuous"], dtype=float)
        restored["binary"] = np.asarray(entry["binary"], dtype=int)
        restored["objectives"] = np.asarray(entry["objectives"], dtype=float)
        archive.append(restored)
    return archive
