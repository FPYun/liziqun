"""
MOPSO-DT 主流程（基于分解和变换的多目标粒子群优化）

用于优化多功能雷达网络在复杂区域的部署。

该算法同时处理：
- 连续变量：2J 个 [0,1] 之间的归一化坐标变量
- 二进制变量：J × N_bin 个 {0,1} 区域编码变量

目标：最大化覆盖率和最小化干扰功率密度
"""

import numpy as np
from typing import Tuple, List, Dict, Callable, Optional, Union
from dataclasses import dataclass
from copy import deepcopy
import logging
from concurrent.futures import ThreadPoolExecutor

from .exceptions import (
    MOPSOError,
    InvalidParameterError,
    EvaluationError,
    ArchiveError
)
from .logger import LogMixin, setup_logger
from .optimization_utils import (
    dominates,
    calculate_crowding_distance,
    batch_update_binary_variables,
    build_decision_matrix,
    NUMBA_AVAILABLE
)


@dataclass
class Particle:
    """
    粒子类，表示雷达部署方案的一个候选解

    决策变量矩阵 Φ 的结构：
    - 连续部分 (2J): [hat_x1, hat_y1, hat_x2, hat_y2, ..., hat_xJ, hat_yJ]
    - 二进制部分 (J × N_bin): 每个雷达节点的区域编码
    """
    # 连续变量部分 (归一化坐标)
    position_continuous: np.ndarray  # 形状: (2J,)
    velocity_continuous: np.ndarray  # 形状: (2J,)

    # 二进制变量部分 (区域编码)
    position_binary: np.ndarray      # 形状: (J, N_bin)

    # 个体历史最优
    pb_continuous: np.ndarray        # 形状: (2J,)
    pb_binary: np.ndarray            # 形状: (J, N_bin)

    # 当前目标函数值 (覆盖率, 干扰功率密度)
    objectives: Optional[np.ndarray] = None  # 形状: (2,)

    # 个体最优目标函数值
    pb_objectives: Optional[np.ndarray] = None  # 形状: (2,)

    def __post_init__(self):
        """初始化后处理：如果没有设置pb，则设为当前位置"""
        if self.pb_continuous is None:
            self.pb_continuous = self.position_continuous.copy()
        if self.pb_binary is None:
            self.pb_binary = self.position_binary.copy()


class MOPSO_DT(LogMixin):
    """
    MOPSO-DT 算法实现类

    基于分解和变换的多目标粒子群优化算法，用于雷达网络部署优化。

    参数说明：
        J: 雷达节点数
        N_bin: 区域编码位数（由分解后的凸多边形数量决定）
        N_P: 粒子群规模（默认50）
        T_max: 最大迭代次数（默认500）
        c_1: 认知学习因子（默认2）
        c_2: 社会学习因子（默认2）
        p_c: 交叉概率（默认0.9）
        archive_size: 外部档案最大容量（默认100）
    """

    def __init__(
        self,
        J: int,
        N_bin: int,
        evaluate_func: Callable[[np.ndarray], np.ndarray],
        N_P: int = 50,
        T_max: int = 500,
        c_1: float = 2.0,
        c_2: float = 2.0,
        p_c: float = 0.9,
        archive_size: int = 100,
        verbose: bool = True,
        log_level: int = logging.INFO,
        use_batch_update: bool = True,
        n_workers: int = 1,
        w_strategy: str = 'legacy',
        p_m_base: float = 0.0,
        select_gb: str = 'random'
    ):
        """
        初始化 MOPSO-DT 优化器

        Args:
            J: 雷达节点数
            N_bin: 区域编码位数
            evaluate_func: 目标函数评估接口，输入决策变量矩阵Φ，返回目标值F
            N_P: 粒子群规模
            T_max: 最大迭代次数
            c_1: 认知学习因子
            c_2: 社会学习因子
            p_c: 交叉概率
            archive_size: 外部档案大小限制
            verbose: 是否显示详细进度
            log_level: 日志级别
            use_batch_update: 是否使用批量更新二进制变量（性能优化）
            w_strategy: 惯性权重策略 ('legacy'=0.4→0.0, 'standard'=0.9→0.4, 'adaptive'=自适应)
            p_m_base: 变异概率下限 (0=使用原始公式 w/N_P)
            select_gb: 全局最优选择策略 ('random'=随机, 'crowding'=拥挤度加权)
        """
        super().__init__()

        # 参数验证
        self._validate_parameters(J, N_bin, N_P, T_max, c_1, c_2, p_c, archive_size)

        # 性能优化选项
        self.use_batch_update = use_batch_update and NUMBA_AVAILABLE
        if use_batch_update and not NUMBA_AVAILABLE:
            self.log_warning("Numba 不可用，批量更新已禁用")

        # 并行评估设置
        self.n_workers = max(1, n_workers)

        self.J = J
        self.N_bin = N_bin
        self.evaluate_func = evaluate_func
        self.N_P = N_P
        self.T_max = T_max
        self.c_1 = c_1
        self.c_2 = c_2
        self.p_c = p_c
        self.archive_size = archive_size
        self.verbose = verbose
        self.w_strategy = w_strategy
        self.p_m_base = p_m_base
        self.select_gb = select_gb

        # 设置日志级别
        self.logger.setLevel(log_level)

        # 决策变量维度
        self.n_continuous = 2 * J  # 连续变量维度
        self.n_binary_total = J * N_bin  # 二进制变量总维度

        # 粒子群
        self.particles: List[Particle] = []

        # 外部档案：存储非劣解
        self.archive: List[Dict] = []  # 每个元素包含 'continuous', 'binary', 'objectives'

        # 全局最优解 gb（从档案中随机选择）
        self.gb_continuous: Optional[np.ndarray] = None
        self.gb_binary: Optional[np.ndarray] = None

        # 迭代历史记录
        self.history: Dict[str, List] = {
            'archive_size': [],
            'crowding_distances': [],
        }

    def _validate_parameters(self, J, N_bin, N_P, T_max, c_1, c_2, p_c, archive_size):
        """验证输入参数的有效性"""
        if J <= 0:
            raise InvalidParameterError("J", J, "正整数")
        if N_bin <= 0:
            raise InvalidParameterError("N_bin", N_bin, "正整数")
        if N_P <= 0:
            raise InvalidParameterError("N_P", N_P, "正整数")
        if T_max <= 0:
            raise InvalidParameterError("T_max", T_max, "正整数")
        if not (0 < c_1 <= 5):
            raise InvalidParameterError("c_1", c_1, "0 < c_1 <= 5")
        if not (0 < c_2 <= 5):
            raise InvalidParameterError("c_2", c_2, "0 < c_2 <= 5")
        if not (0 < p_c <= 1):
            raise InvalidParameterError("p_c", p_c, "0 < p_c <= 1")
        if archive_size < 10:
            raise InvalidParameterError("archive_size", archive_size, ">= 10")

    # =========================================================================
    # 核心算法流程
    # =========================================================================

    def optimize(self) -> Tuple[List[Dict], Dict]:
        """
        执行 MOPSO-DT 优化主流程

        Returns:
            archive: 最终的非劣解档案
            stats: 优化过程统计信息

        Raises:
            EvaluationError: 当评估函数执行失败时
            ArchiveError: 当档案操作失败时
        """
        self.log_info("=" * 70)
        self.log_info("MOPSO-DT 优化算法启动")
        self.log_info("=" * 70)
        self.log_info(f"参数配置: J={self.J}, N_bin={self.N_bin}, N_P={self.N_P}, T_max={self.T_max}")
        self.log_info(f"学习因子: c_1={self.c_1}, c_2={self.c_2}, 交叉概率: p_c={self.p_c}")
        self.log_info(f"惯性策略: {self.w_strategy}, 变异下限: {self.p_m_base}, 选择策略: {self.select_gb}")
        self.log_info(f"性能优化: Numba={NUMBA_AVAILABLE}, 批量更新={self.use_batch_update}")

        if self.verbose:
            print("=" * 70)
            print("MOPSO-DT 优化算法")
            print("=" * 70)
            print(f"参数配置:")
            print(f"  雷达节点数 J: {self.J}")
            print(f"  区域编码位数 N_bin: {self.N_bin}")
            print(f"  粒子群规模 N_P: {self.N_P}")
            print(f"  最大迭代次数 T_max: {self.T_max}")
            print(f"  学习因子: c_1={self.c_1}, c_2={self.c_2}")
            print(f"  交叉概率 p_c: {self.p_c}")
            print(f"  惯性策略: {self.w_strategy}, 变异下限: {self.p_m_base}, 选择策略: {self.select_gb}")
            print(f"  档案大小限制: {self.archive_size}")
            print(f"  性能优化: Numba={'启用' if NUMBA_AVAILABLE else '未启用'}, "
                  f"批量更新={'启用' if self.use_batch_update else '未启用'}, "
                  f"并行线程={self.n_workers}")
            print("-" * 70)

        try:
            # 步骤1: 初始化
            self._initialize()

            # 步骤2: 评估与初始归档
            self._evaluate_and_archive()

            # 步骤3: 主循环迭代
            for t in range(1, self.T_max + 1):
                # 计算动态参数
                w = self._calculate_inertia_weight(t)
                p_m = self._calculate_mutation_probability(w)

                # 环境维护：计算拥挤度并修剪档案
                self._maintain_archive()

                # 从档案中选择全局最优 gb
                self._select_global_best()

                # 更新连续变量（PSO速度-位置更新）
                self._update_continuous_variables(w)

                # 更新二进制变量（交叉+变异）
                self._update_binary_variables(p_m)

                # 评估新位置并更新最优解
                self._evaluate_and_update_best()

                # 记录历史
                self.history['archive_size'].append(len(self.archive))

                # 显示进度
                if self.verbose and t % 50 == 0:
                    print(f"迭代 {t:4d}/{self.T_max}: 档案大小={len(self.archive):3d}, w={w:.4f}, p_m={p_m:.6f}")

            # 最终维护档案
            self._maintain_archive()

            self.log_info("优化完成!")
            self.log_info(f"最终档案大小: {len(self.archive)}")

            if self.verbose:
                print("-" * 70)
                print("优化完成!")
                print(f"最终档案大小: {len(self.archive)}")
                print("=" * 70)

            # 生成统计信息
            stats = self._generate_stats()

            return self.archive, stats

        except Exception as e:
            self.log_error(f"优化过程出错: {str(e)}")
            raise MOPSOError(f"优化失败: {str(e)}") from e

    # =========================================================================
    # 步骤1: 初始化
    # =========================================================================

    def _initialize(self):
        """
        初始化粒子群

        生成 N_P 个粒子：
        - 连续变量：随机初始化为 [0,1] 之间的实数
        - 二进制变量：随机初始化为 0 或 1
        - 速度 V = 0
        - 当前位置设为个体历史最优位置 pb
        """
        self.log_info("开始初始化粒子群...")
        self.particles = []

        for i in range(self.N_P):
            try:
                # 连续变量：随机初始化在 [0, 1]
                pos_cont = np.random.uniform(0, 1, size=self.n_continuous)
                vel_cont = np.zeros(self.n_continuous)

                # 二进制变量：随机初始化为 0 或 1
                pos_bin = np.random.randint(0, 2, size=(self.J, self.N_bin))

                # 创建粒子（pb 初始化为当前位置）
                particle = Particle(
                    position_continuous=pos_cont,
                    velocity_continuous=vel_cont,
                    position_binary=pos_bin,
                    pb_continuous=pos_cont.copy(),
                    pb_binary=pos_bin.copy()
                )

                self.particles.append(particle)
            except Exception as e:
                self.log_error(f"初始化粒子 {i} 失败: {str(e)}")
                raise MOPSOError(f"粒子初始化失败: {str(e)}") from e

        self.log_info(f"初始化完成: 生成 {self.N_P} 个粒子")

        if self.verbose:
            print(f"初始化完成: 生成 {self.N_P} 个粒子")

    # =========================================================================
    # 步骤2: 评估与初始归档
    # =========================================================================

    def _evaluate_and_archive(self):
        """
        评估所有粒子并进行初始归档

        流程：
        1. 对每个粒子，调用 evaluate_func 评估目标函数值
        2. 将当前解存入外部档案
        3. 进行非劣排序，找出非劣解
        4. 从档案中随机选择一个解作为全局最优 gb
        """
        self.log_info("开始初始评估...")

        failed_count = 0

        for idx, particle in enumerate(self.particles):
            try:
                objectives = self._evaluate_particle(particle, particle_idx=idx)
                particle.objectives = objectives
                particle.pb_objectives = objectives.copy()
                self._add_to_archive(
                    particle.position_continuous.copy(),
                    particle.position_binary.copy(),
                    objectives.copy()
                )
            except EvaluationError as e:
                failed_count += 1
                self.log_warning(f"粒子 {idx} 评估失败: {e}")
                particle.objectives = np.array([0.0, float('inf')])
                particle.pb_objectives = particle.objectives.copy()

        if failed_count > 0:
            self.log_warning(f"共有 {failed_count}/{self.N_P} 个粒子评估失败")

        # 初始非劣排序
        self._nondominated_sorting()

        # 随机选择全局最优
        self._select_global_best()

        self.log_info(f"初始评估完成: 档案大小={len(self.archive)}")

        if self.verbose:
            print(f"初始评估完成: 档案大小={len(self.archive)}")

    def _evaluate_particle(self, particle: Particle, particle_idx: Optional[int] = None) -> np.ndarray:
        """
        评估单个粒子的目标函数值

        Args:
            particle: 待评估的粒子
            particle_idx: 粒子索引（用于错误报告）

        Returns:
            objectives: 目标函数值向量 [coverage, interference]

        Raises:
            EvaluationError: 当评估函数执行失败时
        """
        try:
            # 构建决策变量矩阵 Φ
            Phi = self._build_decision_matrix(
                particle.position_continuous,
                particle.position_binary
            )

            # 验证决策变量矩阵
            if not np.all((Phi[:, :2] >= 0) & (Phi[:, :2] <= 1)):
                raise EvaluationError(
                    f"归一化坐标超出[0,1]范围",
                    particle_idx=particle_idx
                )

            # 调用评估函数
            objectives = self.evaluate_func(Phi)

            # 验证返回值
            if not isinstance(objectives, np.ndarray):
                raise EvaluationError(
                    f"评估函数必须返回numpy.ndarray，实际返回{type(objectives)}",
                    particle_idx=particle_idx
                )

            if objectives.shape != (2,):
                raise EvaluationError(
                    f"评估函数返回值形状应为(2,)，实际为{objectives.shape}",
                    particle_idx=particle_idx
                )

            return objectives

        except Exception as e:
            if isinstance(e, EvaluationError):
                raise
            self.log_error(f"评估粒子{particle_idx}时出错: {str(e)}")
            raise EvaluationError(f"评估失败: {str(e)}", particle_idx=particle_idx) from e

    def _evaluate_particles_parallel(self, particles: List[Particle]) -> List[Tuple[Optional[np.ndarray], Optional[str]]]:
        """并行评估多个粒子，按批次分组到各线程，返回 (objectives, error) 列表"""
        n = len(particles)
        if self.n_workers <= 1 or n <= self.n_workers:
            # 粒子太少，直接串行
            results = []
            for idx, particle in enumerate(particles):
                try:
                    objectives = self._evaluate_particle(particle, particle_idx=idx)
                    results.append((objectives, None))
                except Exception as e:
                    results.append((None, str(e)))
            return results

        # 把粒子分成 n_workers 组，每组在一个线程里串行评估
        chunks = np.array_split(np.arange(n), self.n_workers)
        all_results = [None] * n

        def _eval_batch(indices):
            for idx in indices:
                try:
                    objectives = self._evaluate_particle(particles[idx], particle_idx=idx)
                    all_results[idx] = (objectives, None)
                except Exception as e:
                    all_results[idx] = (None, str(e))

        with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
            list(executor.map(_eval_batch, chunks))

        return all_results

    def _update_particle_best(self, particle: Particle, new_objectives: np.ndarray):
        """更新粒子的个体最优 pb"""
        if particle.pb_objectives is None:
            particle.pb_continuous = particle.position_continuous.copy()
            particle.pb_binary = particle.position_binary.copy()
            particle.pb_objectives = new_objectives.copy()
        elif self._dominates(new_objectives, particle.pb_objectives):
            particle.pb_continuous = particle.position_continuous.copy()
            particle.pb_binary = particle.position_binary.copy()
            particle.pb_objectives = new_objectives.copy()
        elif not self._dominates(particle.pb_objectives, new_objectives):
            if np.random.random() < 0.5:
                particle.pb_continuous = particle.position_continuous.copy()
                particle.pb_binary = particle.position_binary.copy()
                particle.pb_objectives = new_objectives.copy()

    def _build_decision_matrix(
        self,
        continuous: np.ndarray,
        binary: np.ndarray
    ) -> np.ndarray:
        """
        构建决策变量矩阵 Φ

        使用 Numba 优化的实现（如果可用）。Φ 的结构：
        [hat_x1, hat_y1, b_11, b_12, ..., b_1N_bin,
         hat_x2, hat_y2, b_21, b_22, ..., b_2N_bin,
         ...
         hat_xJ, hat_yJ, b_J1, b_J2, ..., b_JN_bin]

        Args:
            continuous: 连续变量 (2J,) 或批量 (N_P, 2J)
            binary: 二进制变量 (J, N_bin) 或批量 (N_P, J, N_bin)

        Returns:
            Phi: 决策变量矩阵 (J, 2 + N_bin) 或批量 (N_P, J, 2 + N_bin)
        """
        return build_decision_matrix(continuous, binary, self.J, self.N_bin)

    # =========================================================================
    # Pareto 非劣解相关操作
    # =========================================================================

    def _dominates(self, obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """
        判断解1是否支配解2（Pareto支配关系）

        使用 Numba 优化的实现（如果可用）。在多目标优化中，解 A 支配解 B 当且仅当：
        1. A 在所有目标上都不劣于 B（即对每个目标 i，f_i(A) ≤ f_i(B)）
        2. A 在至少一个目标上严格优于 B（即存在某个目标 j，f_j(A) < f_j(B)）

        注意：本问题中目标1（覆盖率）需要最大化，目标2（干扰）需要最小化
        因此我们在内部将覆盖率取负，统一转化为最小化问题

        Args:
            obj1: 解1的目标函数值 [coverage1, interference1]
            obj2: 解2的目标函数值 [coverage2, interference2]

        Returns:
            True if obj1 dominates obj2, False otherwise
        """
        return dominates(obj1, obj2)

    def _add_to_archive(
        self,
        continuous: np.ndarray,
        binary: np.ndarray,
        objectives: np.ndarray
    ):
        """
        将解加入外部档案

        Args:
            continuous: 连续变量
            binary: 二进制变量
            objectives: 目标函数值
        """
        solution = {
            'continuous': continuous,
            'binary': binary,
            'objectives': objectives,
            'crowding_distance': 0.0  # 将在后续计算
        }
        self.archive.append(solution)

    def _nondominated_sorting(self):
        """
        执行非劣排序，从档案中移除被支配的解

        算法逻辑：
        1. 遍历档案中的所有解对
        2. 标记被支配的解
        3. 只保留非劣解（不被任何其他解支配的解）
        """
        if len(self.archive) <= 1:
            return

        dominated = [False] * len(self.archive)

        for i in range(len(self.archive)):
            if dominated[i]:
                continue
            for j in range(len(self.archive)):
                if i == j or dominated[j]:
                    continue

                # 检查 i 是否支配 j
                if self._dominates(
                    self.archive[i]['objectives'],
                    self.archive[j]['objectives']
                ):
                    dominated[j] = True
                # 检查 j 是否支配 i
                elif self._dominates(
                    self.archive[j]['objectives'],
                    self.archive[i]['objectives']
                ):
                    dominated[i] = True
                    break  # i 被支配，无需继续检查

        # 只保留非劣解
        self.archive = [
            self.archive[i] for i in range(len(self.archive))
            if not dominated[i]
        ]

    def _calculate_crowding_distance(self) -> np.ndarray:
        """
        计算档案中非劣解的拥挤度距离（Crowding Distance）

        使用 Numba 优化的实现（如果可用）。拥挤度距离用于衡量解在目标空间中的分布密度：
        - 距离越大，表示解周围的密度越小，多样性越好
        - 距离越小，表示解周围的密度越大，越容易被淘汰

        计算步骤：
        1. 对每个目标函数，将解按该目标值排序
        2. 边界解（该目标的最大和最小值）的拥挤度设为无穷大
        3. 中间解的拥挤度为该目标上相邻两个解的归一化距离之和
        4. 对所有目标重复上述过程，累加得到最终拥挤度

        Returns:
            distances: 每个解的拥挤度距离数组
        """
        n_solutions = len(self.archive)
        if n_solutions <= 2:
            return np.full(n_solutions, np.inf)

        # 获取目标函数值矩阵
        objectives = np.array([sol['objectives'] for sol in self.archive])

        # 使用 Numba 优化的实现
        return calculate_crowding_distance(objectives)

    def _maintain_archive(self):
        """
        维护外部档案：计算拥挤度并按降序排列，删除多余解

        流程：
        1. 执行非劣排序，确保只保留非劣解
        2. 如果档案大小超过限制：
           a. 计算所有解的拥挤度距离
           b. 按拥挤度降序排列（距离大的优先保留）
           c. 截断至 archive_size
        """
        # 非劣排序
        self._nondominated_sorting()

        # 如果档案大小超过限制，基于拥挤度截断
        if len(self.archive) > self.archive_size:
            # 计算拥挤度
            distances = self._calculate_crowding_distance()

            # 按拥挤度降序排列（距离大的优先保留）
            sorted_indices = np.argsort(distances)[::-1]

            # 截断档案
            self.archive = [self.archive[i] for i in sorted_indices[:self.archive_size]]

            # 记录拥挤度
            self.history['crowding_distances'].append(distances[sorted_indices[:self.archive_size]])

    def _select_global_best(self):
        """
        从外部档案中选择全局最优解 gb

        策略：
        - 'random': 随机选择一个非劣解
        - 'crowding': 拥挤度加权轮盘赌（拥挤度大的被选概率高，促进多样性）
        """
        if not self.archive:
            return

        if self.select_gb == 'crowding' and len(self.archive) > 2:
            distances = self._calculate_crowding_distance()
            # 将 inf 替换为一个大有限值，避免 NaN
            finite_max = np.max(distances[np.isfinite(distances)]) if np.any(np.isfinite(distances)) else 1.0
            distances = np.where(np.isfinite(distances), distances, finite_max * 10)
            total = distances.sum()
            if total > 0:
                probs = distances / total
                probs = np.nan_to_num(probs, nan=1.0/len(self.archive))
                probs = probs / probs.sum()  # 归一化
                idx = np.random.choice(len(self.archive), p=probs)
            else:
                idx = np.random.randint(0, len(self.archive))
        else:
            idx = np.random.randint(0, len(self.archive))

        selected = self.archive[idx]
        self.gb_continuous = selected['continuous'].copy()
        self.gb_binary = selected['binary'].copy()

    # =========================================================================
    # 参数计算
    # =========================================================================

    def _calculate_inertia_weight(self, t: int) -> float:
        """
        计算动态惯性权重

        策略：
        - 'legacy':   w = -0.4/T_max * t + 0.4        (0.4 → 0.0)
        - 'standard': w = 0.9 - 0.5 * t/T_max          (0.9 → 0.4)
        - 'adaptive': w = 0.9 - 0.5 * (t/T_max)^0.5    (0.9 → 0.4, 前期下降慢)

        Args:
            t: 当前迭代次数

        Returns:
            w: 惯性权重
        """
        if self.w_strategy == 'standard':
            return 0.9 - 0.5 * t / self.T_max
        elif self.w_strategy == 'adaptive':
            return 0.9 - 0.5 * (t / self.T_max) ** 0.5
        else:  # legacy
            return -0.4 / self.T_max * t + 0.4

    def _calculate_mutation_probability(self, w: float) -> float:
        """
        计算动态变异概率

        公式: p_m = max(p_m_base, w / N_P)

        Args:
            w: 当前惯性权重

        Returns:
            p_m: 变异概率
        """
        return max(self.p_m_base, w / self.N_P)

    # =========================================================================
    # 步骤3: 变量更新
    # =========================================================================

    def _update_continuous_variables(self, w: float):
        """
        更新连续变量（PSO速度-位置更新）

        使用标准PSO公式：
        v_new = w × v + c_1 × r_1 × (pb - x) + c_2 × r_2 × (gb - x)
        x_new = x + v_new

        其中：
        - w: 惯性权重
        - c_1, c_2: 学习因子
        - r_1, r_2: [0,1] 之间的随机数
        - pb: 个体最优位置
        - gb: 全局最优位置

        更新后使用截断（Clipping）确保 x ∈ [0, 1]

        Args:
            w: 惯性权重
        """
        for particle in self.particles:
            # 生成随机数（向量化）
            r1 = np.random.uniform(0, 1, size=self.n_continuous)
            r2 = np.random.uniform(0, 1, size=self.n_continuous)

            # 速度更新: v = w*v + c1*r1*(pb - x) + c2*r2*(gb - x)
            cognitive = self.c_1 * r1 * (particle.pb_continuous - particle.position_continuous)
            social = self.c_2 * r2 * (self.gb_continuous - particle.position_continuous)

            particle.velocity_continuous = (
                w * particle.velocity_continuous + cognitive + social
            )

            # 位置更新: x = x + v
            particle.position_continuous = particle.position_continuous + particle.velocity_continuous

            # 截断操作：确保在 [0, 1] 范围内
            particle.position_continuous = np.clip(
                particle.position_continuous, 0.0, 1.0
            )

    def _update_binary_variables(self, p_m: float):
        """
        更新二进制变量（交叉 + 变异）

        使用批量更新优化（如果启用了 Numba 优化）。对于每个二进制位 b_ij：

        1. 交叉（Crossover）：
           - 生成 r_3 ~ U(0,1)
           - 若 r_3 < p_c（交叉概率），触发交叉
           - 生成 r_4 ~ U(0,1)
           - 若 r_4 < c_1 / (c_1 + c_2)，继承 pb 的二进制位
           - 否则，继承 gb 的二进制位

        2. 变异（Mutation）：
           - 若未触发交叉，生成 r_5 ~ U(0,1)
           - 若 r_5 < p_m（变异概率），对二进制位取反

        Args:
            p_m: 变异概率
        """
        c_ratio = self.c_1 / (self.c_1 + self.c_2)

        # 使用批量更新优化（Numba 加速）
        if self.use_batch_update:
            # 收集所有粒子的二进制位置
            positions_binary = np.array([p.position_binary for p in self.particles])
            pb_binary = np.array([p.pb_binary for p in self.particles])

            # 批量更新
            new_positions = batch_update_binary_variables(
                positions_binary, pb_binary, self.gb_binary,
                self.p_c, p_m, c_ratio
            )

            # 更新粒子
            for i, particle in enumerate(self.particles):
                particle.position_binary = new_positions[i]
        else:
            # 原始逐个更新（兼容模式）
            for particle in self.particles:
                for j in range(self.J):
                    for k in range(self.N_bin):
                        # 生成 r_3
                        r3 = np.random.random()

                        if r3 < self.p_c:
                            # 触发交叉
                            r4 = np.random.random()
                            if r4 < c_ratio:
                                # 继承 pb 的二进制位
                                particle.position_binary[j, k] = particle.pb_binary[j, k]
                            else:
                                # 继承 gb 的二进制位
                                assert self.gb_binary is not None, "gb_binary should be initialized"
                                particle.position_binary[j, k] = self.gb_binary[j, k]
                        else:
                            # 未触发交叉，检查变异
                            r5 = np.random.random()
                            if r5 < p_m:
                                # 取反操作
                                particle.position_binary[j, k] = 1 - particle.position_binary[j, k]

    def _evaluate_and_update_best(self):
        """
        评估新位置并更新最优解

        流程：
        1. 重新评估所有粒子的目标函数值 F
        2. 更新个体最优 pb：
           - 若新位置支配原 pb，则替换
           - 若互不支配，随机选择（或保持原pb）
        3. 将新解加入外部档案
        4. 更新全局档案和 gb
        """
        for particle in self.particles:
            new_objectives = self._evaluate_particle(particle)
            particle.objectives = new_objectives
            self._update_particle_best(particle, new_objectives)
            self._add_to_archive(
                particle.position_continuous.copy(),
                particle.position_binary.copy(),
                new_objectives.copy()
            )

    # =========================================================================
    # 统计和输出
    # =========================================================================

    def _generate_stats(self) -> Dict:
        """
        生成优化过程统计信息

        Returns:
            stats: 包含各种统计信息的字典
        """
        if not self.archive:
            return {}

        objectives = np.array([sol['objectives'] for sol in self.archive])

        stats = {
            'final_archive_size': len(self.archive),
            'coverage_max': np.max(objectives[:, 0]),
            'coverage_min': np.min(objectives[:, 0]),
            'coverage_mean': np.mean(objectives[:, 0]),
            'interference_max': np.max(objectives[:, 1]),
            'interference_min': np.min(objectives[:, 1]),
            'interference_mean': np.mean(objectives[:, 1]),
            'history': self.history
        }

        return stats

    def get_pareto_front(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        获取最终的 Pareto 前沿

        Returns:
            continuous_solutions: 所有非劣解的连续变量 (N, 2J)
            binary_solutions: 所有非劣解的二进制变量 (N, J, N_bin)
            objectives: 所有非劣解的目标值 (N, 2)
        """
        if not self.archive:
            return np.array([]), np.array([]), np.array([])

        n = len(self.archive)
        continuous = np.array([sol['continuous'] for sol in self.archive])
        binary = np.array([sol['binary'] for sol in self.archive])
        objectives = np.array([sol['objectives'] for sol in self.archive])

        return continuous, binary, objectives


# =============================================================================
# 评估函数接口示例
# =============================================================================

def example_evaluate_func(Phi: np.ndarray) -> np.ndarray:
    """
    示例评估函数

    该函数接收决策变量矩阵 Φ，执行坐标变换并计算目标函数值。

    Args:
        Phi: 决策变量矩阵 (J, 2+N_bin)
             每行: [hat_x, hat_y, b_1, b_2, ..., b_N_bin]

    Returns:
        objectives: [覆盖率, 干扰功率密度]
    """
    # 这里应该调用实际的坐标变换和目标计算
    # 简化示例：随机返回目标值
    coverage = np.random.uniform(0.5, 1.0)
    interference = np.random.uniform(0, 0.5)
    return np.array([coverage, interference])


# =============================================================================
# 使用示例
# =============================================================================

def example_usage():
    """MOPSO-DT 使用示例"""
    print("=" * 70)
    print("MOPSO-DT 算法示例")
    print("=" * 70)

    # 算法参数
    J = 5           # 5个雷达节点
    N_bin = 3       # 3位区域编码（最多8个凸区域）
    N_P = 30        # 30个粒子
    T_max = 200     # 200次迭代

    # 创建优化器
    mopso = MOPSO_DT(
        J=J,
        N_bin=N_bin,
        evaluate_func=example_evaluate_func,
        N_P=N_P,
        T_max=T_max,
        c_1=2.0,
        c_2=2.0,
        p_c=0.9,
        archive_size=50,
        verbose=True
    )

    # 执行优化
    archive, stats = mopso.optimize()

    # 输出结果
    print("\n优化结果统计:")
    print(f"  最终档案大小: {stats['final_archive_size']}")
    print(f"  覆盖率范围: [{stats['coverage_min']:.4f}, {stats['coverage_max']:.4f}]")
    print(f"  干扰范围: [{stats['interference_min']:.4f}, {stats['interference_max']:.4f}]")

    # 获取 Pareto 前沿
    cont, binary, objs = mopso.get_pareto_front()
    print(f"\nPareto 前沿解数量: {len(objs)}")

    # 显示前3个解
    print("\n前3个非劣解:")
    for i in range(min(3, len(objs))):
        print(f"  解 {i+1}: 覆盖率={objs[i, 0]:.4f}, 干扰={objs[i, 1]:.4f}")

    return mopso, archive, stats


if __name__ == "__main__":
    # 运行示例
    mopso, archive, stats = example_usage()
