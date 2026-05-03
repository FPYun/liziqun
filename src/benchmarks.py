"""
标准多目标优化测试函数

用于验证 MOPSO-DT 算法正确性。

参考文献：
    Zitzler, Deb, Thiele (2000). Comparison of Multiobjective Evolutionary Algorithms.
    Schaffer (1985). Multiple Objective Optimization with Vector Evaluated Genetic Algorithms.
"""

import numpy as np


def schaffer_n1(x):
    """Schaffer N.1 双目标测试函数

    f1 = x²
    f2 = (x-2)²
    Pareto 前沿: x ∈ [0, 2]
    """
    f1 = x[0] ** 2
    f2 = (x[0] - 2) ** 2
    return np.array([f1, f2])


def zdt1(x):
    """ZDT1 双目标测试函数（30 变量）

    f1 = x₁
    f2 = g · (1 - √(f₁/g))
    其中 g = 1 + 9/(n-1) · Σ_{i=2}^n xᵢ
    Pareto 前沿: f₂ = 1 - √f₁, f₁ ∈ [0, 1]
    """
    n = len(x)
    f1 = x[0]
    g = 1.0 + 9.0 / (n - 1) * np.sum(x[1:])
    f2 = g * (1.0 - np.sqrt(f1 / g))
    return np.array([f1, f2])


def zdt2(x):
    """ZDT2 双目标测试函数（30 变量）

    f1 = x₁
    f2 = g · (1 - (f₁/g)²)
    其中 g = 1 + 9/(n-1) · Σ_{i=2}^n xᵢ
    Pareto 前沿: f₂ = 1 - f₁², f₁ ∈ [0, 1]
    """
    n = len(x)
    f1 = x[0]
    g = 1.0 + 9.0 / (n - 1) * np.sum(x[1:])
    f2 = g * (1.0 - (f1 / g) ** 2)
    return np.array([f1, f2])


def make_benchmark_evaluate(benchmark_func, n_vars):
    """将基准函数包装为 MOPSO evaluate_func 接口

    Args:
        benchmark_func: 基准函数 (如 zdt1)
        n_vars: 变量总数

    Returns:
        evaluate_func: Φ -> objectives
    """
    def evaluate_func(Phi):
        x = Phi[:, :2].flatten()
        if len(x) < n_vars:
            x = np.concatenate([x, np.zeros(n_vars - len(x))])
        else:
            x = x[:n_vars]
        return benchmark_func(x)
    return evaluate_func


def find_knee_point(objectives):
    """在 Pareto 前沿上找到拐点（平衡点）

    拐点 = argmin(f1² + f2²)，即离原点最近的解。

    Args:
        objectives: (N, 2) 数组

    Returns:
        knee_idx: 拐点索引
    """
    normalized = objectives.copy()
    f1_range = normalized[:, 0].max() - normalized[:, 0].min()
    f2_range = normalized[:, 1].max() - normalized[:, 1].min()
    if f1_range > 0:
        normalized[:, 0] = (normalized[:, 0] - normalized[:, 0].min()) / f1_range
    if f2_range > 0:
        normalized[:, 1] = (normalized[:, 1] - normalized[:, 1].min()) / f2_range
    return np.argmin(normalized[:, 0] ** 2 + normalized[:, 1] ** 2)


def get_extreme_points(objectives):
    """获取 Pareto 前沿上的极值点

    Returns:
        best_cov_idx: 最佳 f1 的索引
        best_int_idx: 最佳 f2 的索引
        knee_idx: 拐点索引
    """
    best_cov_idx = np.argmin(objectives[:, 0])  # 最小化 f1
    best_int_idx = np.argmin(objectives[:, 1])  # 最小化 f2
    knee_idx = find_knee_point(objectives)
    return best_cov_idx, best_int_idx, knee_idx


def sample_representative_solutions(objectives, n_samples=6):
    """沿 Pareto 前沿均匀采样代表性解

    Args:
        objectives: (N, 2) 数组
        n_samples: 采样数量

    Returns:
        indices: 采样解的索引列表
    """
    sorted_idx = np.argsort(objectives[:, 0])
    indices = np.linspace(0, len(sorted_idx) - 1, n_samples, dtype=int)
    return [sorted_idx[i] for i in indices]
