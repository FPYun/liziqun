"""
性能优化工具模块

使用 Numba JIT 编译加速 MOPSO-DT 的核心计算函数

依赖：
    - numba: JIT 编译加速
    - numpy: 数值计算

注意：
    如果 numba 不可用，会自动回退到纯 NumPy 实现
"""

import numpy as np
from typing import Tuple, List

# 尝试导入 numba
try:
    from numba import jit, njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # 创建装饰器占位符
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range


# ============================================================================
# Pareto 支配关系计算（Numba 加速）
# ============================================================================

if NUMBA_AVAILABLE:
    @njit(cache=True)
    def _dominates_numba(obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """
        Numba 加速的 Pareto 支配判断

        参数:
            obj1: 解1的目标函数值 [coverage1, interference1]
            obj2: 解2的目标函数值 [coverage2, interference2]

        返回:
            True if obj1 dominates obj2
        """
        # 两个目标都是最小化问题（f1 = 1-ECR, f2 = J_norm）
        # 检查条件1：obj1 在所有目标上都不劣于 obj2
        not_worse = (obj1[0] <= obj2[0]) and (obj1[1] <= obj2[1])

        # 检查条件2：obj1 在至少一个目标上严格优于 obj2
        strictly_better = (obj1[0] < obj2[0]) or (obj1[1] < obj2[1])

        return not_worse and strictly_better


    @njit(cache=True)
    def _calculate_crowding_distance_numba(objectives: np.ndarray) -> np.ndarray:
        """
        Numba 加速的拥挤度距离计算

        参数:
            objectives: 目标函数值矩阵 (n_solutions, n_objectives)

        返回:
            distances: 每个解的拥挤度距离
        """
        n_solutions = objectives.shape[0]
        n_objectives = objectives.shape[1]

        if n_solutions <= 2:
            distances = np.empty(n_solutions)
            distances.fill(np.inf)
            return distances

        distances = np.zeros(n_solutions)

        for m in range(n_objectives):
            # 按第 m 个目标排序
            sorted_indices = np.argsort(objectives[:, m])

            # 边界解设为无穷大
            distances[sorted_indices[0]] = np.inf
            distances[sorted_indices[-1]] = np.inf

            # 计算该目标的值域
            f_max = objectives[sorted_indices[-1], m]
            f_min = objectives[sorted_indices[0], m]

            if abs(f_max - f_min) < 1e-10:
                continue

            # 计算中间解的拥挤度
            for i in range(1, n_solutions - 1):
                idx = sorted_indices[i]
                prev_idx = sorted_indices[i - 1]
                next_idx = sorted_indices[i + 1]

                # 归一化距离
                distance_contrib = (
                    objectives[next_idx, m] - objectives[prev_idx, m]
                ) / (f_max - f_min)

                distances[idx] += distance_contrib

        return distances


    @njit(cache=True)
    def _update_binary_variables_numba(
        position_binary: np.ndarray,
        pb_binary: np.ndarray,
        gb_binary: np.ndarray,
        p_c: float,
        p_m: float,
        c_ratio: float
    ) -> np.ndarray:
        """
        Numba 加速的二进制变量更新（单个粒子）

        参数:
            position_binary: 当前二进制位置 (J, N_bin)
            pb_binary: 个体最优二进制位置 (J, N_bin)
            gb_binary: 全局最优二进制位置 (J, N_bin)
            p_c: 交叉概率
            p_m: 变异概率
            c_ratio: c_1 / (c_1 + c_2)

        返回:
            new_position: 更新后的二进制位置
        """
        J, N_bin = position_binary.shape
        new_position = position_binary.copy()

        for j in range(J):
            for k in range(N_bin):
                r3 = np.random.random()

                if r3 < p_c:
                    # 触发交叉
                    r4 = np.random.random()
                    if r4 < c_ratio:
                        new_position[j, k] = pb_binary[j, k]
                    else:
                        new_position[j, k] = gb_binary[j, k]

                # 变异（独立于交叉）
                r5 = np.random.random()
                if r5 < p_m:
                    new_position[j, k] = 1 - position_binary[j, k]

        return new_position


    @njit(cache=True, parallel=True)
    def _batch_update_binary_variables_numba(
        positions_binary: np.ndarray,
        pb_binary: np.ndarray,
        gb_binary: np.ndarray,
        p_c: float,
        p_m: float,
        c_ratio: float
    ) -> np.ndarray:
        """
        Numba 加速的二进制变量批量更新（并行版本）

        参数:
            positions_binary: 所有粒子的二进制位置 (N_P, J, N_bin)
            pb_binary: 所有粒子的个体最优 (N_P, J, N_bin)
            gb_binary: 全局最优 (J, N_bin)
            p_c: 交叉概率
            p_m: 变异概率
            c_ratio: c_1 / (c_1 + c_2)

        返回:
            new_positions: 更新后的所有粒子二进制位置
        """
        N_P = positions_binary.shape[0]
        new_positions = positions_binary.copy()

        for p in prange(N_P):
            for j in range(positions_binary.shape[1]):
                for k in range(positions_binary.shape[2]):
                    r3 = np.random.random()

                    if r3 < p_c:
                        r4 = np.random.random()
                        if r4 < c_ratio:
                            new_positions[p, j, k] = pb_binary[p, j, k]
                        else:
                            new_positions[p, j, k] = gb_binary[j, k]

                    # 变异（独立于交叉）
                    r5 = np.random.random()
                    if r5 < p_m:
                        new_positions[p, j, k] = 1 - positions_binary[p, j, k]

        return new_positions


    @njit(cache=True)
    def _build_decision_matrix_numba(
        continuous: np.ndarray,
        binary: np.ndarray,
        J: int,
        N_bin: int
    ) -> np.ndarray:
        """
        Numba 加速的决策变量矩阵构建

        参数:
            continuous: 连续变量 (2J,)
            binary: 二进制变量 (J, N_bin)
            J: 雷达节点数
            N_bin: 二进制编码位数

        返回:
            Phi: 决策变量矩阵 (J, 2 + N_bin)
        """
        Phi = np.zeros((J, 2 + N_bin))

        for j in range(J):
            Phi[j, 0] = continuous[2 * j]
            Phi[j, 1] = continuous[2 * j + 1]
            for k in range(N_bin):
                Phi[j, 2 + k] = binary[j, k]

        return Phi


    @njit(cache=True, parallel=True)
    def _batch_build_decision_matrix_numba(
        continuous_batch: np.ndarray,
        binary_batch: np.ndarray,
        J: int,
        N_bin: int
    ) -> np.ndarray:
        """
        Numba 加速的批量决策变量矩阵构建

        参数:
            continuous_batch: 连续变量批次 (N_P, 2J)
            binary_batch: 二进制变量批次 (N_P, J, N_bin)
            J: 雷达节点数
            N_bin: 二进制编码位数

        返回:
            Phi_batch: 决策变量矩阵批次 (N_P, J, 2 + N_bin)
        """
        N_P = continuous_batch.shape[0]
        Phi_batch = np.zeros((N_P, J, 2 + N_bin))

        for p in prange(N_P):
            for j in range(J):
                Phi_batch[p, j, 0] = continuous_batch[p, 2 * j]
                Phi_batch[p, j, 1] = continuous_batch[p, 2 * j + 1]
                for k in range(N_bin):
                    Phi_batch[p, j, 2 + k] = binary_batch[p, j, k]

        return Phi_batch


# ============================================================================
# 纯 NumPy 实现（回退方案）
# ============================================================================

def _dominates_numpy(obj1: np.ndarray, obj2: np.ndarray) -> bool:
    """纯 NumPy 实现的 Pareto 支配判断（两个目标均为最小化）"""
    not_worse = (obj1[0] <= obj2[0]) and (obj1[1] <= obj2[1])
    strictly_better = (obj1[0] < obj2[0]) or (obj1[1] < obj2[1])
    return not_worse and strictly_better


def _calculate_crowding_distance_numpy(objectives: np.ndarray) -> np.ndarray:
    """纯 NumPy 实现的拥挤度距离计算"""
    n_solutions = objectives.shape[0]

    if n_solutions <= 2:
        distances = np.full(n_solutions, np.inf)
        return distances

    distances = np.zeros(n_solutions)

    for m in range(objectives.shape[1]):
        sorted_indices = np.argsort(objectives[:, m])
        distances[sorted_indices[0]] = np.inf
        distances[sorted_indices[-1]] = np.inf

        f_max = objectives[sorted_indices[-1], m]
        f_min = objectives[sorted_indices[0], m]

        if abs(f_max - f_min) < 1e-10:
            continue

        for i in range(1, n_solutions - 1):
            idx = sorted_indices[i]
            prev_idx = sorted_indices[i - 1]
            next_idx = sorted_indices[i + 1]

            distance_contrib = (
                objectives[next_idx, m] - objectives[prev_idx, m]
            ) / (f_max - f_min)

            distances[idx] += distance_contrib

    return distances


# ============================================================================
# 公共 API
# ============================================================================

def dominates(obj1: np.ndarray, obj2: np.ndarray) -> bool:
    """
    Pareto 支配判断（自动选择最优实现）

    Args:
        obj1: 解1的目标函数值 [coverage1, interference1]
        obj2: 解2的目标函数值 [coverage2, interference2]

    Returns:
        True if obj1 dominates obj2
    """
    if NUMBA_AVAILABLE:
        return _dominates_numba(obj1, obj2)
    else:
        return _dominates_numpy(obj1, obj2)


def calculate_crowding_distance(objectives: np.ndarray) -> np.ndarray:
    """
    计算拥挤度距离（自动选择最优实现）

    Args:
        objectives: 目标函数值矩阵 (n_solutions, n_objectives)

    Returns:
        distances: 每个解的拥挤度距离
    """
    if NUMBA_AVAILABLE:
        return _calculate_crowding_distance_numba(objectives)
    else:
        return _calculate_crowding_distance_numpy(objectives)


def batch_update_binary_variables(
    positions_binary: np.ndarray,
    pb_binary: np.ndarray,
    gb_binary: np.ndarray,
    p_c: float,
    p_m: float,
    c_ratio: float
) -> np.ndarray:
    """
    批量更新二进制变量（自动选择最优实现）

    Args:
        positions_binary: 所有粒子的二进制位置 (N_P, J, N_bin)
        pb_binary: 所有粒子的个体最优 (N_P, J, N_bin)
        gb_binary: 全局最优 (J, N_bin)
        p_c: 交叉概率
        p_m: 变异概率
        c_ratio: c_1 / (c_1 + c_2)

    Returns:
        new_positions: 更新后的所有粒子二进制位置
    """
    if NUMBA_AVAILABLE:
        return _batch_update_binary_variables_numba(
            positions_binary, pb_binary, gb_binary, p_c, p_m, c_ratio
        )
    else:
        # 纯 NumPy 实现
        N_P, J, N_bin = positions_binary.shape
        new_positions = positions_binary.copy()

        # 生成所有随机数
        r3 = np.random.random((N_P, J, N_bin))
        r4 = np.random.random((N_P, J, N_bin))
        r5 = np.random.random((N_P, J, N_bin))

        # 交叉掩码
        crossover_mask = r3 < p_c
        pb_mask = r4 < c_ratio

        # 应用交叉
        new_positions = np.where(
            crossover_mask,
            np.where(pb_mask, pb_binary, gb_binary),
            new_positions
        )

        # 变异掩码（仅在未交叉时）
        mutation_mask = (~crossover_mask) & (r5 < p_m)
        new_positions = np.where(
            mutation_mask,
            1 - positions_binary,
            new_positions
        )

        return new_positions


def build_decision_matrix(
    continuous: np.ndarray,
    binary: np.ndarray,
    J: int,
    N_bin: int
) -> np.ndarray:
    """
    构建决策变量矩阵（自动选择最优实现）

    Args:
        continuous: 连续变量 (2J,) 或 (N_P, 2J)
        binary: 二进制变量 (J, N_bin) 或 (N_P, J, N_bin)
        J: 雷达节点数
        N_bin: 二进制编码位数

    Returns:
        Phi: 决策变量矩阵
    """
    if continuous.ndim == 1:
        # 单个粒子
        if NUMBA_AVAILABLE:
            return _build_decision_matrix_numba(continuous, binary, J, N_bin)
        else:
            Phi = np.zeros((J, 2 + N_bin))
            for j in range(J):
                Phi[j, 0] = continuous[2 * j]
                Phi[j, 1] = continuous[2 * j + 1]
                Phi[j, 2:] = binary[j, :]
            return Phi
    else:
        # 批量
        if NUMBA_AVAILABLE:
            return _batch_build_decision_matrix_numba(continuous, binary, J, N_bin)
        else:
            N_P = continuous.shape[0]
            Phi_batch = np.zeros((N_P, J, 2 + N_bin))
            for p in range(N_P):
                for j in range(J):
                    Phi_batch[p, j, 0] = continuous[p, 2 * j]
                    Phi_batch[p, j, 1] = continuous[p, 2 * j + 1]
                    Phi_batch[p, j, 2:] = binary[p, j, :]
            return Phi_batch


# ============================================================================
# 性能测试和诊断
# ============================================================================

def benchmark_functions():
    """运行性能基准测试"""
    import time

    print("=" * 60)
    print("优化函数性能基准测试")
    print("=" * 60)
    print(f"Numba 可用: {NUMBA_AVAILABLE}")
    print()

    # 测试数据
    n_solutions = 100
    n_objectives = 2
    objectives = np.random.random((n_solutions, n_objectives))

    print(f"测试数据规模: {n_solutions} 个解, {n_objectives} 个目标")
    print()

    # 测试拥挤度计算
    print("1. 拥挤度距离计算:")

    # Numba 版本（第一次调用会编译）
    if NUMBA_AVAILABLE:
        start = time.time()
        _ = _calculate_crowding_distance_numba(objectives)
        compile_time = time.time() - start
        print(f"   编译+运行时间: {compile_time:.4f}s")

        start = time.time()
        for _ in range(100):
            _ = _calculate_crowding_distance_numba(objectives)
        numba_time = (time.time() - start) / 100
        print(f"   Numba 平均时间: {numba_time:.6f}s")

    # NumPy 版本
    start = time.time()
    for _ in range(100):
        _ = _calculate_crowding_distance_numpy(objectives)
    numpy_time = (time.time() - start) / 100
    print(f"   NumPy 平均时间: {numpy_time:.6f}s")

    if NUMBA_AVAILABLE:
        speedup = numpy_time / numba_time
        print(f"   加速比: {speedup:.2f}x")

    print()
    print("2. Pareto 支配判断:")

    obj1 = np.array([0.9, 0.2])
    obj2 = np.array([0.8, 0.3])

    if NUMBA_AVAILABLE:
        start = time.time()
        for _ in range(10000):
            _ = _dominates_numba(obj1, obj2)
        numba_time = (time.time() - start) / 10000
        print(f"   Numba 平均时间: {numba_time:.9f}s")

    start = time.time()
    for _ in range(10000):
        _ = _dominates_numpy(obj1, obj2)
    numpy_time = (time.time() - start) / 10000
    print(f"   NumPy 平均时间: {numpy_time:.9f}s")

    if NUMBA_AVAILABLE:
        speedup = numpy_time / numba_time
        print(f"   加速比: {speedup:.2f}x")

    print()
    print("=" * 60)


def get_optimizer_info() -> dict:
    """获取优化器信息"""
    return {
        'numba_available': NUMBA_AVAILABLE,
        'optimized_functions': [
            'dominates',
            'calculate_crowding_distance',
            'batch_update_binary_variables',
            'build_decision_matrix'
        ]
    }


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    benchmark_functions()
