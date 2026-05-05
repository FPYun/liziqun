"""
HybridMOPSO: CPU+GPU 并发评估的 MOPSO-DT 扩展

将粒子分为两组：
- GPU 组 (~80%): 串行调用 CuPy 加速的 evaluate_func（GPU 已饱和）
- CPU 组 (~20%): 并行调用纯 NumPy 的 cpu_evaluate_func（多线程）

两组通过 ThreadPoolExecutor 同时执行，减少墙钟时间。
"""

import numpy as np
from typing import List, Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os as _os

from .mopso import MOPSO_DT, Particle
from .evaluation import (
    RadarConfig, TaskPoint,
    decode_particle, binary_to_polygon_index,
    _get_radar_physical_positions,
    GPU_AVAILABLE,
)
from .coordinate_transform import transform_coordinates
from .exceptions import EvaluationError


# ============================================================================
# 纯 NumPy 评估函数（用于 CPU 并行，不依赖 CuPy）
# ============================================================================

def _calc_detection_matrix_simple_np(radar_xy, task_xy, radar_configs):
    """纯 NumPy：向量化计算探测概率矩阵 (M, J)"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=2))
    P0_arr = np.array([c.P0 for c in radar_configs])[np.newaxis, :]
    beta_arr = np.array([c.beta for c in radar_configs])[np.newaxis, :]
    return np.clip(P0_arr * np.exp(-beta_arr * dist), 0.0, 1.0)


def _calc_jamming_matrix_simple_np(radar_xy, task_xy, radar_configs):
    """纯 NumPy：向量化计算干扰功率密度矩阵 (M, J)"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=2))
    dist = np.maximum(dist, 1e-9)
    alpha_arr = np.array([c.alpha_air if c.is_air else c.alpha_ground
                          for c in radar_configs])[np.newaxis, :]
    P0_arr = np.array([c.P0 for c in radar_configs])[np.newaxis, :]
    return P0_arr / (4 * np.pi * (dist ** alpha_arr))


def _calc_detection_matrix_radar_eq_np(radar_xy, task_xy, radar_configs):
    """纯 NumPy：雷达方程模型探测概率矩阵 (M, J)"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist_km = np.sqrt(np.sum(diff ** 2, axis=2))
    dist_m = np.maximum(dist_km * 1000.0, 1e-3)

    J_count = radar_xy.shape[0]
    R_max_arr = np.array([c.R_max for c in radar_configs])[np.newaxis, :]
    within_range = dist_km <= R_max_arr

    k_B = 1.38e-23
    T0 = 290.0
    denominator_base = ((4 * np.pi) ** 3) * k_B * T0

    numerators = np.empty(J_count)
    D0_linear = np.empty(J_count)
    bw_arr = np.empty(J_count)
    for i, c in enumerate(radar_configs):
        G_lin = 10 ** (c.G_t_dB / 10.0)
        numerators[i] = c.P_t * (G_lin ** 2) * (c.wavelength ** 2) * c.sigma
        D0_linear[i] = 10 ** (c.D0_dB / 10.0)
        bw_arr[i] = c.bandwidth

    SNR = numerators[np.newaxis, :] / (denominator_base * bw_arr[np.newaxis, :] * (dist_m ** 4))
    P_detect = np.exp(-D0_linear[np.newaxis, :] / (1.0 + SNR))
    P_detect = np.clip(P_detect, 0.0, 1.0)
    P_detect = np.where(within_range, P_detect, 0.0)
    return P_detect


def _calc_jamming_matrix_radar_eq_np(radar_xy, task_xy, radar_configs):
    """纯 NumPy：雷达方程模型干扰功率密度矩阵 (M, J)"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist_km = np.sqrt(np.sum(diff ** 2, axis=2))
    dist_m = np.maximum(dist_km * 1000.0, 1e-3)

    J_count = radar_xy.shape[0]
    powers = np.empty(J_count)
    gains = np.empty(J_count)
    for i, c in enumerate(radar_configs):
        powers[i] = c.jammer_P_t
        gains[i] = 10 ** (c.jammer_G_t_dB / 10.0)

    return powers[np.newaxis, :] * gains[np.newaxis, :] / (4 * np.pi * (dist_m ** 2))


def calculate_ecr_np(radar_positions, task_points, radar_configs,
                      convex_polygons=None, binary_codes=None, continuous_coords=None):
    """纯 NumPy 版本的 ECR 计算"""
    M = len(task_points)
    J = len(radar_positions)
    if M == 0 or J == 0:
        return 0.0

    radar_xy = _get_radar_physical_positions(
        radar_positions, radar_configs, convex_polygons, binary_codes, continuous_coords
    )
    task_xy = np.array([(t.x, t.y) for t in task_points])
    priorities = np.array([t.priority for t in task_points])

    if radar_configs[0].use_radar_equation:
        P_detect = _calc_detection_matrix_radar_eq_np(radar_xy, task_xy, radar_configs)
    else:
        P_detect = _calc_detection_matrix_simple_np(radar_xy, task_xy, radar_configs)

    P_joint = 1.0 - np.prod(1.0 - P_detect, axis=1)
    covered = (P_joint >= radar_configs[0].P_min).astype(float)
    total_priority = priorities.sum()
    return float(np.sum(covered * priorities) / total_priority) if total_priority > 0 else 0.0


def calculate_jamming_density_np(jammer_positions, task_points, jammer_configs,
                                   convex_polygons=None, binary_codes=None, continuous_coords=None):
    """纯 NumPy 版本的最小干扰功率密度计算"""
    M = len(task_points)
    J = len(jammer_positions)
    if M == 0 or J == 0:
        return 0.0

    radar_xy = _get_radar_physical_positions(
        jammer_positions, jammer_configs, convex_polygons, binary_codes, continuous_coords
    )
    task_xy = np.array([(t.x, t.y) for t in task_points])

    if jammer_configs[0].use_radar_equation:
        J_mat = _calc_jamming_matrix_radar_eq_np(radar_xy, task_xy, jammer_configs)
    else:
        J_mat = _calc_jamming_matrix_simple_np(radar_xy, task_xy, jammer_configs)

    total_power = np.sum(J_mat, axis=1)
    return float(np.min(total_power))


def evaluate_deployment_np(Phi, task_points, radar_configs, convex_polygons, J, N_bin):
    """纯 NumPy 版本的部署评估函数"""
    continuous = Phi[:, :2].flatten()
    binary = Phi[:, 2:2 + N_bin]

    positions = decode_particle(continuous, binary, J, N_bin, convex_polygons)
    positions_array = np.array(positions)

    ECR = calculate_ecr_np(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons, binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )
    J_min = calculate_jamming_density_np(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons, binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    f1 = 1.0 - ECR
    f2 = 1.0 / J_min if J_min > 1e-10 else 1e10
    return np.array([f1, f2])


def evaluate_deployment_normalized_np(Phi, task_points, radar_configs, convex_polygons,
                                       J, N_bin, J_max_ref=0.01):
    """纯 NumPy 版本的归一化部署评估函数"""
    continuous = Phi[:, :2].flatten()
    binary = Phi[:, 2:2 + N_bin]

    positions = decode_particle(continuous, binary, J, N_bin, convex_polygons)
    positions_array = np.array(positions)

    ECR = calculate_ecr_np(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons, binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )
    J_min = calculate_jamming_density_np(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons, binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    f1 = 1.0 - ECR
    f2 = J_min / (J_min + J_max_ref + 1e-10)
    return np.array([f1, f2])


def create_cpu_evaluate_function(task_points, radar_configs, convex_polygons, J, N_bin):
    """创建纯 NumPy 评估函数（用于 CPU 并行线程）"""
    def evaluate_func(Phi):
        return evaluate_deployment_np(
            Phi, task_points, radar_configs, convex_polygons, J, N_bin
        )
    return evaluate_func


def create_cpu_normalized_evaluate_function(task_points, radar_configs, convex_polygons,
                                              J, N_bin, J_max_ref=0.01):
    """创建纯 NumPy 归一化评估函数（用于 CPU 并行线程）"""
    def evaluate_func(Phi):
        return evaluate_deployment_normalized_np(
            Phi, task_points, radar_configs, convex_polygons, J, N_bin, J_max_ref
        )
    return evaluate_func


# ============================================================================
# HybridMOPSO 类
# ============================================================================

class HybridMOPSO(MOPSO_DT):
    """
    CPU+GPU 混合并发的 MOPSO-DT 优化器

    在每轮迭代中，将粒子分为两组同时评估：
    - GPU 组 (gpu_fraction): 串行使用 CuPy 加速的 evaluate_func
    - CPU 组 (剩余): 并行使用纯 NumPy 的 cpu_evaluate_func

    额外参数：
        cpu_evaluate_func: 纯 NumPy 评估函数（必需）
        gpu_fraction: GPU 处理的粒子比例（默认 0.8）
        n_cpu_workers: CPU 并行线程数（默认 4）
    """

    def __init__(
        self,
        J: int,
        N_bin: int,
        evaluate_func,
        cpu_evaluate_func,
        N_P: int = 50,
        T_max: int = 500,
        c_1: float = 2.0,
        c_2: float = 2.0,
        p_c: float = 0.9,
        archive_size: int = 100,
        verbose: bool = True,
        log_level: int = logging.INFO,
        use_batch_update: bool = True,
        w_strategy: str = 'legacy',
        p_m_base: float = 0.0,
        select_gb: str = 'random',
        gpu_fraction: float = 0.8,
        n_cpu_workers: int = 4,
    ):
        super().__init__(
            J=J, N_bin=N_bin, evaluate_func=evaluate_func,
            N_P=N_P, T_max=T_max, c_1=c_1, c_2=c_2, p_c=p_c,
            archive_size=archive_size, verbose=verbose, log_level=log_level,
            use_batch_update=use_batch_update,
            w_strategy=w_strategy, p_m_base=p_m_base, select_gb=select_gb,
        )
        self.cpu_evaluate_func = cpu_evaluate_func
        self.gpu_fraction = float(gpu_fraction) if GPU_AVAILABLE else 0.0
        self.n_cpu_workers = max(1, n_cpu_workers)

        if not GPU_AVAILABLE and self.gpu_fraction > 0:
            self.log_info("CuPy 不可用，回退到全 CPU 并行评估")

    def _evaluate_and_archive(self):
        """混合并行评估所有粒子并初始归档"""
        self.log_info("开始初始评估（混合 CPU+GPU）...")
        results = self._evaluate_particles_hybrid(self.particles)

        failed_count = 0
        for idx, (obj, err) in enumerate(results):
            particle = self.particles[idx]
            if err:
                failed_count += 1
                self.log_warning(f"粒子 {idx} 评估失败: {err}")
                particle.objectives = np.array([0.0, float('inf')])
                particle.pb_objectives = particle.objectives.copy()
            else:
                particle.objectives = obj
                particle.pb_objectives = obj.copy()
                self._add_to_archive(
                    particle.position_continuous.copy(),
                    particle.position_binary.copy(),
                    obj.copy()
                )

        if failed_count > 0:
            self.log_warning(f"共有 {failed_count}/{self.N_P} 个粒子评估失败")

        self._nondominated_sorting()
        self._select_global_best()
        self.log_info(f"初始评估完成: 档案大小={len(self.archive)}")

        if self.verbose:
            print(f"初始评估完成: 档案大小={len(self.archive)}")

    def _evaluate_and_update_best(self):
        """混合并行评估新位置并更新最优解"""
        results = self._evaluate_particles_hybrid(self.particles)

        for idx, (obj, err) in enumerate(results):
            if err is not None:
                continue
            particle = self.particles[idx]
            particle.objectives = obj
            self._update_particle_best(particle, obj)
            self._add_to_archive(
                particle.position_continuous.copy(),
                particle.position_binary.copy(),
                obj.copy()
            )

    def _evaluate_particles_hybrid(self, particles):
        """
        CPU+GPU 混合并行评估粒子

        分组策略：
        - GPU 组: particles[:n_gpu]，1 个 future 串行评估
        - CPU 组: particles[n_gpu:]，n_cpu_workers 个 future 并行评估
        - 两组同时提交到 ThreadPoolExecutor
        """
        n = len(particles)
        n_gpu = max(0, int(n * self.gpu_fraction))
        n_cpu = n - n_gpu

        gpu_particles = particles[:n_gpu]
        cpu_particles = particles[n_gpu:]

        results = [None] * n

        # 确定 worker 数量: GPU 1 个 + CPU n_cpu_workers 个
        total_workers = (1 if gpu_particles else 0) + (min(len(cpu_particles), self.n_cpu_workers) if cpu_particles else 0)
        if total_workers == 0:
            return results

        with ThreadPoolExecutor(max_workers=max(1, total_workers)) as executor:
            future_map = {}

            # GPU 组：一个 future 串行评估全部 GPU 粒子
            if gpu_particles:
                future_map[executor.submit(
                    self._eval_gpu_batch, gpu_particles
                )] = list(range(n_gpu))

            # CPU 组：分成 n_cpu_workers 批，每批一个 future
            if cpu_particles:
                cpu_indices = list(range(n_gpu, n))
                chunks = np.array_split(cpu_indices, min(len(cpu_particles), self.n_cpu_workers))
                for chunk in chunks:
                    if len(chunk) == 0:
                        continue
                    chunk_particles = [particles[i] for i in chunk]
                    future_map[executor.submit(
                        self._eval_cpu_batch, chunk_particles
                    )] = list(chunk)

            for future in as_completed(future_map):
                indices = future_map[future]
                try:
                    batch_results = future.result()
                    for i, (obj, err) in zip(indices, batch_results):
                        results[i] = (obj, err)
                except Exception as e:
                    for i in indices:
                        results[i] = (None, str(e))

        return results

    def _eval_gpu_batch(self, particles):
        """串行评估一组 GPU 粒子（使用 CuPy 加速的 evaluate_func）"""
        batch_results = []
        for idx, p in enumerate(particles):
            try:
                obj = self._evaluate_particle(p, particle_idx=idx)
                batch_results.append((obj, None))
            except Exception as e:
                batch_results.append((None, str(e)))
        return batch_results

    def _eval_cpu_batch(self, particles):
        """串行评估一组 CPU 粒子（使用纯 NumPy 的 cpu_evaluate_func）"""
        batch_results = []
        for p in particles:
            try:
                Phi = self._build_decision_matrix(
                    p.position_continuous, p.position_binary
                )
                if not np.all((Phi[:, :2] >= 0) & (Phi[:, :2] <= 1)):
                    raise ValueError("归一化坐标超出[0,1]范围")
                obj = self.cpu_evaluate_func(Phi)
                if not isinstance(obj, np.ndarray) or obj.shape != (2,):
                    raise ValueError(f"评估函数返回值异常: {obj}")
                batch_results.append((obj, None))
            except Exception as e:
                batch_results.append((None, str(e)))
        return batch_results
