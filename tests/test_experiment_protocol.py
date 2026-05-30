import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from experiments.compare_algorithms import (
    METHOD_FACTORIES,
    build_scenario,
    expected_evaluation_budget,
)


def test_algorithm_comparison_methods_share_same_budget():
    scenario = build_scenario("challenging")
    budget = expected_evaluation_budget(N_P=10, T_max=5)

    for method_name in METHOD_FACTORIES:
        optimizer = METHOD_FACTORIES[method_name](
            scenario=scenario,
            N_P=10,
            T_max=5,
            seed=2026,
        )
        _, stats = optimizer.optimize()
        assert stats["evaluations"] == budget
