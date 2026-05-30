import numpy as np
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.baseline_algorithms import MOEAD_DT, NSGA2_DT, RandomSearchMO, SPEA2_DT


def simple_evaluate(Phi):
    continuous = Phi[:, :2]
    f1 = float(np.mean(continuous[:, 0]))
    f2 = float(np.mean(1.0 - continuous[:, 1]))
    return np.array([f1, f2])


def assert_archive_contract(archive, J=3, N_bin=2):
    assert len(archive) > 0
    for entry in archive:
        assert entry["continuous"].shape == (2 * J,)
        assert entry["binary"].shape == (J, N_bin)
        assert entry["objectives"].shape == (2,)
        assert np.all(entry["continuous"] >= 0.0)
        assert np.all(entry["continuous"] <= 1.0)
        assert set(np.unique(entry["binary"])).issubset({0, 1})


def test_all_baseline_algorithms_return_archive_contract():
    algorithms = [
        RandomSearchMO,
        NSGA2_DT,
        MOEAD_DT,
        SPEA2_DT,
    ]

    for algorithm_cls in algorithms:
        optimizer = algorithm_cls(
            J=3,
            N_bin=2,
            evaluate_func=simple_evaluate,
            N_P=12,
            T_max=4,
            archive_size=20,
            seed=2026,
        )

        archive, stats = optimizer.optimize()

        assert_archive_contract(archive)
        assert stats["evaluations"] == 12 * 4


def test_baseline_algorithms_are_reproducible_with_fixed_seed():
    first = NSGA2_DT(
        J=3,
        N_bin=2,
        evaluate_func=simple_evaluate,
        N_P=12,
        T_max=4,
        archive_size=20,
        seed=2026,
    ).optimize()[0]
    second = NSGA2_DT(
        J=3,
        N_bin=2,
        evaluate_func=simple_evaluate,
        N_P=12,
        T_max=4,
        archive_size=20,
        seed=2026,
    ).optimize()[0]

    first_obj = np.array([entry["objectives"] for entry in first])
    second_obj = np.array([entry["objectives"] for entry in second])

    assert np.allclose(first_obj, second_obj)
