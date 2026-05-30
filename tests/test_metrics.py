import numpy as np
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import (
    calculate_hypervolume_2d,
    calculate_spacing,
    filter_nondominated,
    summarize_metric_records,
)


def test_filter_nondominated_removes_dominated_points():
    objectives = np.array(
        [
            [0.10, 0.90],
            [0.20, 0.80],
            [0.30, 0.70],
            [0.40, 0.90],
            [0.30, 0.95],
        ]
    )

    indices = filter_nondominated(objectives)

    assert indices == [0, 1, 2]


def test_hypervolume_2d_uses_union_area_for_minimization_front():
    objectives = np.array([[0.20, 0.80], [0.50, 0.40]])

    hv = calculate_hypervolume_2d(objectives, ref_point=(1.0, 1.0))

    assert hv == np.float64(0.36)


def test_spacing_is_zero_for_evenly_spaced_front():
    objectives = np.array([[0.0, 1.0], [0.5, 0.5], [1.0, 0.0]])

    spacing = calculate_spacing(objectives)

    assert spacing == 0.0


def test_summarize_metric_records_groups_mean_and_std_by_method_and_scenario():
    records = [
        {"scenario": "challenging", "method": "ours", "hv": 0.4, "runtime": 10.0},
        {"scenario": "challenging", "method": "ours", "hv": 0.6, "runtime": 14.0},
        {"scenario": "challenging", "method": "random", "hv": 0.1, "runtime": 2.0},
    ]

    summary = summarize_metric_records(records, metric_names=["hv", "runtime"])

    ours = next(
        item
        for item in summary
        if item["scenario"] == "challenging" and item["method"] == "ours"
    )
    assert ours["n"] == 2
    assert ours["hv_mean"] == 0.5
    assert np.isclose(ours["hv_std"], 0.1)
    assert ours["runtime_mean"] == 12.0
