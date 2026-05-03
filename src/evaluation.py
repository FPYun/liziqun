"""
目标函数评估模块

实现多功能雷达/电子对抗网络的覆盖评估和干扰评估

功能：
1. ECR（有效覆盖率）计算 - 感知效能
2. 干扰功率密度计算 - 压制效能
3. 空地协同传播模型（区分A2G和G2G链路）
4. 多目标综合评估

依赖：
- numpy: 数值计算
- shapely: 几何计算
- cupy (可选): GPU 加速
"""

import os as _os
import numpy as np

# GPU 加速：优先使用 CuPy，回退到 NumPy
# Windows 中文路径修复：在 import cupy 前设置环境变量到 ASCII 路径
if _os.name == 'nt':
    for _k, _v in {
        'TMP': 'C:/temp', 'TEMP': 'C:/temp',
        'CUPY_CACHE_DIR': 'C:/cupy_cache',
        'CUDA_PATH': _os.path.expandvars(
            r'%APPDATA%\Python\Python313\site-packages\nvidia'),
    }.items():
        _os.environ[_k] = _v
    for _d in ['C:/temp', 'C:/cupy_cache']:
        _os.makedirs(_d, exist_ok=True)

GPU_AVAILABLE = False
try:
    import cupy as cp
    GPU_AVAILABLE = True
except ImportError:
    cp = None

# 统一接口：有 CuPy 时 xp=cupy，否则 xp=numpy
xp = cp if GPU_AVAILABLE else np

# Windows 中文路径深度修复：设置 NVRTC 头文件路径（如需）
if GPU_AVAILABLE and _os.name == 'nt':
    try:
        _CLEAN_INCLUDE = 'C:/cupy_include'
        if not _os.path.isdir(_CLEAN_INCLUDE) or not _os.listdir(_CLEAN_INCLUDE):
            import shutil as _shutil
            _cupy_dir = _os.path.dirname(cp.__file__)
            _src_cupy = _os.path.join(_cupy_dir, '_core', 'include')
            if _os.path.isdir(_src_cupy):
                _os.makedirs(_CLEAN_INCLUDE, exist_ok=True)
                _shutil.copytree(_src_cupy, _CLEAN_INCLUDE, dirs_exist_ok=True)
        from cupy.cuda import compiler as _compiler
        _original_get_opts = _compiler._get_extra_include_dir_opts
        def _patched_get_extra_include_dir_opts():
            return _original_get_opts() + (f'-I{_CLEAN_INCLUDE}',)
        _compiler._get_extra_include_dir_opts = _patched_get_extra_include_dir_opts
    except Exception:
        pass  # 静默失败，大部分情况下不需要此修复
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass
from shapely.geometry import Polygon, Point

# 尝试导入坐标变换模块
try:
    from .coordinate_transform import transform_coordinates, is_convex_polygon
    COORD_TRANSFORM_AVAILABLE = True
except ImportError:
    COORD_TRANSFORM_AVAILABLE = False


# ============================================================================
# 配置参数
# ============================================================================

@dataclass
class RadarConfig:
    """雷达/干扰源配置参数"""
    # 探测/干扰参数（简化模型）
    P0: float = 0.95          # 最大探测/干扰概率（近距离）
    P_min: float = 0.8       # 最小可接受概率阈值
    beta: float = 0.01       # 衰减系数

    # 传播模型参数
    alpha_air: float = 2.0   # 空-地链路路径损耗指数 (2.0~2.5)
    alpha_ground: float = 4.0  # 地-地链路路径损耗指数 (3.5~4.0)

    # 雷达位置类型
    is_air: bool = False     # True=空中节点(UAV), False=地面节点

    # 雷达方程参数（参考论文4.1节）
    P_t: float = 3000.0      # 雷达发射功率 (W) - 参考论文: 3kW
    G_t_dB: float = 50.0     # 天线增益 (dB) - 参考论文: 50dB
    wavelength: float = 0.3  # 信号波长 (m) - 参考论文: 0.3m
    sigma: float = 0.1       # 目标RCS (m²) - 参考论文: 0.1m²
    bandwidth: float = 15e6  # 信号带宽 (Hz) - 参考论文: 15MHz
    D0_dB: float = 12.5      # 检测因子 (dB) - 参考论文: 12.5dB
    P_fa: float = 1e-6       # 虚警概率
    R_max: float = 60.0      # 最大探测距离 (km) - 参考论文: 60km
    jammer_P_t: float = 150.0  # 干扰机发射功率 (W) - 参考论文: 150W
    jammer_G_t_dB: float = 30.0  # 干扰机天线增益 (dB) - 参考论文: 30dB
    use_radar_equation: bool = False  # 是否使用雷达方程模型


@dataclass
class TaskPoint:
    """任务点定义"""
    x: float
    y: float
    priority: float = 1.0     # 优先级权重


# ============================================================================
# 传播模型
# ============================================================================

def path_loss_air_to_ground(d: float, alpha: float = 2.0) -> float:
    """
    空-地链路(A2G)路径损耗模型

    近似自由空间传播，受多径衰落影响小

    Args:
        d: 欧氏距离
        alpha: 路径损耗指数 (2.0~2.5)

    Returns:
        路径损耗 L_path(d) ∝ d^alpha
    """
    if d < 1e-9:
        return 1.0
    return d ** alpha


def path_loss_ground_to_ground(d: float, alpha: float = 4.0, shadowing: float = 0.0) -> float:
    """
    地-地链路(G2G)路径损耗模型

    受地形遮挡和多径效应严重影响

    Args:
        d: 欧氏距离
        alpha: 路径损耗指数 (3.5~4.0)
        shadowing: 阴影衰落（对数正态分布随机变量）

    Returns:
        路径损耗 L_path(d) ∝ d^(alpha+ξσ)
    """
    if d < 1e-9:
        return 1.0
    return (d ** alpha) * np.exp(shadowing)


def calculate_reception_probability(
    radar_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    config: RadarConfig
) -> float:
    """
    计算雷达对目标的探测概率

    使用概率探测模型：
    P_detect = P0 * exp(-beta * d)  if d <= R_max
             = 0                    if d > R_max

    Args:
        radar_pos: 雷达位置 (x, y)
        target_pos: 目标位置 (x, y)
        config: 雷达配置参数

    Returns:
        探测概率 P_detect ∈ [0, 1]
    """
    # 计算欧氏距离
    dx = radar_pos[0] - target_pos[0]
    dy = radar_pos[1] - target_pos[1]
    d = np.sqrt(dx**2 + dy**2)

    # 根据雷达类型选择路径损耗模型
    if config.is_air:
        # 空-地链路：自由空间传播
        path_loss = path_loss_air_to_ground(d, config.alpha_air)
    else:
        # 地-地链路：受遮挡影响
        path_loss = path_loss_ground_to_ground(d, config.alpha_ground)

    # 探测概率模型
    P_detect = config.P0 * np.exp(-config.beta * d)

    return np.clip(P_detect, 0.0, 1.0)


def calculate_jamming_power(
    jammer_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    config: RadarConfig
) -> float:
    """
    计算干扰源在目标处的功率密度

    J = P * G / (4π * d^alpha)

    Args:
        jammer_pos: 干扰源位置 (x, y)
        target_pos: 目标位置 (x, y)
        config: 干扰源配置参数

    Returns:
        干扰功率密度 J
    """
    # 计算欧氏距离
    dx = jammer_pos[0] - target_pos[0]
    dy = jammer_pos[1] - target_pos[1]
    d = np.sqrt(dx**2 + dy**2)

    if d < 1e-9:
        return config.P0  # 近距离假设

    # 根据干扰源类型选择路径损耗
    if config.is_air:
        alpha = config.alpha_air
    else:
        alpha = config.alpha_ground

    # 干扰功率密度（非相干叠加）
    # J = P * G / (4π * d^alpha)
    J = config.P0 / (4 * np.pi * (d ** alpha))

    return J


# ============================================================================
# 雷达方程模型（参考论文4.1节参数）
# ============================================================================

def calculate_reception_probability_radar_eq(
    radar_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    config: RadarConfig
) -> float:
    """
    基于雷达方程的探测概率计算

    参考论文模型：
    SNR = (P_t * G^2 * λ^2 * σ) / ((4π)^3 * k * T0 * B * d^4)
    P_d = exp(-D0 / (1 + SNR))  (简化近似)

    其中：
    - P_t: 发射功率 (W)
    - G: 天线增益（线性值）
    - λ: 波长 (m)
    - σ: 目标RCS (m²)
    - k: 玻尔兹曼常数 1.38e-23 J/K
    - T0: 标准温度 290K
    - B: 带宽 (Hz)
    - d: 距离 (m)
    - D0: 检测因子（线性值）

    Args:
        radar_pos: 雷达位置 (x, y) km
        target_pos: 目标位置 (x, y) km
        config: 雷达配置参数

    Returns:
        探测概率 P_detect ∈ [0, 1]
    """
    dx = radar_pos[0] - target_pos[0]
    dy = radar_pos[1] - target_pos[1]
    d_km = np.sqrt(dx**2 + dy**2)

    # 最大探测距离检查
    if d_km > config.R_max:
        return 0.0

    d_m = d_km * 1000.0  # km -> m

    # 物理常数
    k_B = 1.38e-23  # 玻尔兹曼常数 J/K
    T0 = 290.0       # 标准温度 K

    # 参数转换
    G_linear = 10 ** (config.G_t_dB / 10.0)  # dB -> 线性值
    D0_linear = 10 ** (config.D0_dB / 10.0)  # dB -> 线性值

    # 雷达方程计算SNR
    numerator = config.P_t * (G_linear ** 2) * (config.wavelength ** 2) * config.sigma
    denominator = ((4 * np.pi) ** 3) * k_B * T0 * config.bandwidth * (d_m ** 4)

    if denominator < 1e-30:
        return 1.0

    SNR = numerator / denominator

    # 探测概率近似：P_d = exp(-D0 / (1 + SNR))
    # 当SNR >> D0时，P_d → 1；当SNR << D0时，P_d → 0
    P_detect = np.exp(-D0_linear / (1.0 + SNR))

    return np.clip(P_detect, 0.0, 1.0)


def calculate_jamming_power_radar_eq(
    jammer_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    config: RadarConfig
) -> float:
    """
    基于干扰方程的干扰功率密度计算

    参考论文模型：
    J = P_t_jammer * G_t_jammer / (4π * d^2)

    其中：
    - P_t_jammer: 干扰机发射功率 (W) - 参考论文: 150W
    - G_t_jammer: 干扰机天线增益（线性值）- 参考论文: 30dB = 1000
    - d: 距离 (m)

    Args:
        jammer_pos: 干扰机位置 (x, y) km
        target_pos: 目标位置 (x, y) km
        config: 干扰机配置参数

    Returns:
        干扰功率密度 J (W/m²)
    """
    dx = jammer_pos[0] - target_pos[0]
    dy = jammer_pos[1] - target_pos[1]
    d_km = np.sqrt(dx**2 + dy**2)

    if d_km < 1e-9:
        return 1e10  # 近距离极大值

    d_m = d_km * 1000.0  # km -> m

    # 干扰机参数
    G_jammer = 10 ** (config.jammer_G_t_dB / 10.0)  # dB -> 线性值

    # 干扰功率密度（自由空间传播，α=2）
    J = config.jammer_P_t * G_jammer / (4 * np.pi * (d_m ** 2))

    return J


# ============================================================================
# 向量化内部函数（NumPy 矩阵运算，消除 Python 循环）
# ============================================================================

def _get_radar_physical_positions(
    radar_positions: np.ndarray,
    radar_configs: List[RadarConfig],
    convex_polygons: Optional[List[Polygon]] = None,
    binary_codes: Optional[np.ndarray] = None,
    continuous_coords: Optional[np.ndarray] = None
) -> np.ndarray:
    """预计算所有雷达的物理位置，返回 (J, 2) 数组"""
    J = len(radar_positions)
    if continuous_coords is not None and convex_polygons is not None:
        positions = np.empty((J, 2))
        for i in range(J):
            hat_x, hat_y = continuous_coords[i, 0], continuous_coords[i, 1]
            poly_idx = binary_to_polygon_index(binary_codes[i])
            if poly_idx < len(convex_polygons):
                x, y = transform_coordinates(convex_polygons[poly_idx], hat_x, hat_y)
            else:
                x, y = radar_positions[i, 0], radar_positions[i, 1]
            positions[i] = [x, y]
        return positions
    return radar_positions[:, :2].copy()


def _to_gpu(arr: np.ndarray):
    """NumPy 数组传到 GPU（如果可用）"""
    return cp.asarray(arr) if GPU_AVAILABLE else arr


def _to_cpu(arr):
    """GPU 数组传回 CPU"""
    return cp.asnumpy(arr) if GPU_AVAILABLE and hasattr(arr, 'get') else arr


def _calc_detection_matrix_simple(
    radar_xy, task_xy, radar_configs: List[RadarConfig]
):
    """向量化计算探测概率矩阵 (M, J)，简化模型。支持 GPU 数组。"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist = xp.sqrt(xp.sum(diff ** 2, axis=2))
    P0_arr = xp.array([c.P0 for c in radar_configs])[np.newaxis, :]
    beta_arr = xp.array([c.beta for c in radar_configs])[np.newaxis, :]
    return xp.clip(P0_arr * xp.exp(-beta_arr * dist), 0.0, 1.0)


def _calc_jamming_matrix_simple(
    radar_xy, task_xy, radar_configs: List[RadarConfig]
):
    """向量化计算干扰功率密度矩阵 (M, J)，简化模型。支持 GPU 数组。"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist = xp.sqrt(xp.sum(diff ** 2, axis=2))
    dist = xp.maximum(dist, 1e-9)
    alpha_arr = xp.array([c.alpha_air if c.is_air else c.alpha_ground
                          for c in radar_configs])[np.newaxis, :]
    P0_arr = xp.array([c.P0 for c in radar_configs])[np.newaxis, :]
    return P0_arr / (4 * np.pi * (dist ** alpha_arr))


def _calc_detection_matrix_radar_eq(
    radar_xy, task_xy, radar_configs: List[RadarConfig]
):
    """向量化计算探测概率矩阵 (M, J)，雷达方程模型。支持 GPU 数组。"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist_km = xp.sqrt(xp.sum(diff ** 2, axis=2))
    dist_m = dist_km * 1000.0
    dist_m = xp.maximum(dist_m, 1e-3)

    J_count = radar_xy.shape[0]
    R_max_arr = xp.array([c.R_max for c in radar_configs])[np.newaxis, :]
    within_range = dist_km <= R_max_arr

    k_B = 1.38e-23
    T0 = 290.0

    numerators = np.empty(J_count)
    D0_linear = np.empty(J_count)
    for i, c in enumerate(radar_configs):
        G_lin = 10 ** (c.G_t_dB / 10.0)
        numerators[i] = c.P_t * (G_lin ** 2) * (c.wavelength ** 2) * c.sigma
        D0_linear[i] = 10 ** (c.D0_dB / 10.0)

    numerators = _to_gpu(numerators[np.newaxis, :])
    D0_linear = _to_gpu(D0_linear[np.newaxis, :])
    denominator_base = ((4 * np.pi) ** 3) * k_B * T0

    bw_arr = xp.array([c.bandwidth for c in radar_configs])[np.newaxis, :]
    SNR = numerators / (denominator_base * bw_arr * (dist_m ** 4))
    P_detect = xp.exp(-D0_linear / (1.0 + SNR))
    P_detect = xp.clip(P_detect, 0.0, 1.0)
    P_detect = xp.where(within_range, P_detect, 0.0)
    return P_detect


def _calc_jamming_matrix_radar_eq(
    radar_xy, task_xy, radar_configs: List[RadarConfig]
):
    """向量化计算干扰功率密度矩阵 (M, J)，雷达方程模型。支持 GPU 数组。"""
    diff = task_xy[:, np.newaxis, :] - radar_xy[np.newaxis, :, :]
    dist_km = xp.sqrt(xp.sum(diff ** 2, axis=2))
    dist_m = xp.maximum(dist_km * 1000.0, 1e-3)

    J_count = radar_xy.shape[0]
    powers = np.empty(J_count)
    gains = np.empty(J_count)
    for i, c in enumerate(radar_configs):
        powers[i] = c.jammer_P_t
        gains[i] = 10 ** (c.jammer_G_t_dB / 10.0)

    powers = _to_gpu(powers[np.newaxis, :])
    gains = _to_gpu(gains[np.newaxis, :])
    return powers * gains / (4 * np.pi * (dist_m ** 2))


# ============================================================================
# ECR（有效覆盖率）计算 - 向量化版本
# ============================================================================

def calculate_ecr(
    radar_positions: np.ndarray,
    task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: Optional[List[Polygon]] = None,
    binary_codes: Optional[np.ndarray] = None,
    continuous_coords: Optional[np.ndarray] = None
) -> float:
    """
    计算有效覆盖率 (Expected Coverage Rate) - GPU 加速版本

    ECR = (1/M) * Σ I(P_joint(m) >= P_th)
    P_joint(m) = 1 - Π(1 - P_detect(i,m))
    """
    M = len(task_points)
    J = len(radar_positions)
    if M == 0 or J == 0:
        return 0.0

    # CPU 端预计算（Shapely 坐标变换）
    radar_xy = _get_radar_physical_positions(
        radar_positions, radar_configs, convex_polygons, binary_codes, continuous_coords
    )
    task_xy = np.array([(t.x, t.y) for t in task_points])
    priorities = np.array([t.priority for t in task_points])

    # 传到 GPU
    radar_xy_g = _to_gpu(radar_xy)
    task_xy_g = _to_gpu(task_xy)

    # 计算探测概率矩阵 (M, J) — 在 GPU 上执行
    if radar_configs[0].use_radar_equation:
        P_detect = _calc_detection_matrix_radar_eq(radar_xy_g, task_xy_g, radar_configs)
    else:
        P_detect = _calc_detection_matrix_simple(radar_xy_g, task_xy_g, radar_configs)

    # OR 融合
    P_joint = 1.0 - xp.prod(1.0 - P_detect, axis=1)

    # 传回 CPU
    P_joint = _to_cpu(P_joint)

    covered = (P_joint >= radar_configs[0].P_min).astype(float)
    total_priority = priorities.sum()
    ECR = float(np.sum(covered * priorities) / total_priority) if total_priority > 0 else 0.0
    return ECR


def calculate_jamming_density(
    jammer_positions: np.ndarray,
    task_points: List[TaskPoint],
    jammer_configs: List[RadarConfig],
    convex_polygons: Optional[List[Polygon]] = None,
    binary_codes: Optional[np.ndarray] = None,
    continuous_coords: Optional[np.ndarray] = None
) -> float:
    """
    计算最小干扰功率密度（用于max-min优化）- GPU 加速版本

    J_min = min_m { Σ_j J_j(m) }
    """
    M = len(task_points)
    J = len(jammer_positions)
    if M == 0 or J == 0:
        return 0.0

    # CPU 端预计算
    radar_xy = _get_radar_physical_positions(
        jammer_positions, jammer_configs, convex_polygons, binary_codes, continuous_coords
    )
    task_xy = np.array([(t.x, t.y) for t in task_points])

    # 传到 GPU
    radar_xy_g = _to_gpu(radar_xy)
    task_xy_g = _to_gpu(task_xy)

    # 计算干扰功率密度矩阵 — 在 GPU 上执行
    if jammer_configs[0].use_radar_equation:
        J_mat = _calc_jamming_matrix_radar_eq(radar_xy_g, task_xy_g, jammer_configs)
    else:
        J_mat = _calc_jamming_matrix_simple(radar_xy_g, task_xy_g, jammer_configs)

    total_power = xp.sum(J_mat, axis=1)

    # 传回 CPU
    total_power = _to_cpu(total_power)
    return float(np.min(total_power))


# ============================================================================
# 二进制编码解码
# ============================================================================

def binary_to_polygon_index(binary_code: np.ndarray) -> int:
    """
    将二进制编码转换为凸多边形索引

    Args:
        binary_code: 二进制编码数组 (N_bin,)

    Returns:
        多边形索引（整数）
    """
    index = 0
    for bit in binary_code:
        index = (index << 1) | int(bit)
    return index


def decode_particle(
    continuous: np.ndarray,
    binary: np.ndarray,
    J: int,
    N_bin: int,
    convex_polygons: List[Polygon]
) -> List[Tuple[float, float]]:
    """
    解码粒子得到物理位置

    Args:
        continuous: 连续变量 (2J,) in [0,1]
        binary: 二进制变量 (J, N_bin)
        J: 雷达数量
        N_bin: 编码位数
        convex_polygons: 凸多边形列表

    Returns:
        物理位置列表 [(x1,y1), (x2,y2), ...]
    """
    positions = []

    for j in range(J):
        # 获取归一化坐标
        hat_x = continuous[2 * j]
        hat_y = continuous[2 * j + 1]

        # 获取二进制编码
        binary_code = binary[j, :]

        # 转换为多边形索引
        poly_idx = binary_to_polygon_index(binary_code)

        # 确保索引在有效范围内
        if poly_idx >= len(convex_polygons):
            poly_idx = poly_idx % len(convex_polygons)

        # 坐标变换
        if COORD_TRANSFORM_AVAILABLE:
            try:
                x, y = transform_coordinates(convex_polygons[poly_idx], hat_x, hat_y)
            except Exception:
                # 如果变换失败，使用多边形中心
                centroid = convex_polygons[poly_idx].centroid
                x, y = centroid.x, centroid.y
        else:
            # 降级：使用多边形中心
            centroid = convex_polygons[poly_idx].centroid
            x, y = centroid.x, centroid.y

        positions.append((x, y))

    return positions


# ============================================================================
# 多目标评估函数
# ============================================================================

def evaluate_deployment(
    Phi: np.ndarray,
    task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: List[Polygon],
    J: int,
    N_bin: int
) -> np.ndarray:
    """
    综合评估函数 - MOPSO调用接口

    计算两个目标：
    1. f1: 1 - ECR (最小化1-覆盖率)
    2. f2: 1/J_min (最小化干扰功率密度的倒数，即最大化J_min)

    Args:
        Phi: 决策变量矩阵 (J, 2+N_bin)
              每行: [hat_x, hat_y, b_1, b_2, ..., b_N_bin]
        task_points: 任务点列表
        radar_configs: 雷达/干扰源配置
        convex_polygons: 凸多边形列表
        J: 雷达数量
        N_bin: 编码位数

    Returns:
        objectives: [1-ECR, 1/J_min] 形状 (2,)
    """
    # 提取连续坐标和二进制编码
    continuous = Phi[:, :2].flatten()  # (2J,)
    binary = Phi[:, 2:2+N_bin]  # (J, N_bin)

    # 解码得到物理位置
    positions = decode_particle(continuous, binary, J, N_bin, convex_polygons)
    positions_array = np.array(positions)

    # 计算ECR（感知效能）
    ECR = calculate_ecr(
        positions_array,
        task_points,
        radar_configs,
        convex_polygons=convex_polygons,
        binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    # 计算最小干扰功率密度（压制效能）
    J_min = calculate_jamming_density(
        positions_array,
        task_points,
        radar_configs,
        convex_polygons=convex_polygons,
        binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    # 目标函数（最小化问题）
    f1 = 1 - ECR  # 最小化1-覆盖率
    f2 = 1.0 / J_min if J_min > 1e-10 else 1e10  # 最小化1/J_min

    return np.array([f1, f2])


def create_evaluate_function(
    task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: List[Polygon],
    J: int,
    N_bin: int
) -> Callable:
    """
    创建评估函数的工厂函数

    用于MOPSO的evaluate_func参数

    Args:
        task_points: 任务点列表
        radar_configs: 雷达配置列表
        convex_polygons: 凸多边形列表
        J: 雷达数量
        N_bin: 编码位数

    Returns:
        评估函数 evaluate_func(Phi) -> np.ndarray
    """
    def evaluate_func(Phi: np.ndarray) -> np.ndarray:
        return evaluate_deployment(
            Phi, task_points, radar_configs, convex_polygons, J, N_bin
        )

    return evaluate_func


# ============================================================================
# 辅助函数
# ============================================================================

def generate_uniform_task_points(
    region: Polygon,
    grid_size: int = 20
) -> List[TaskPoint]:
    """
    在区域内生成均匀分布的任务点

    Args:
        region: 区域多边形
        grid_size: 网格密度

    Returns:
        任务点列表
    """
    minx, miny, maxx, maxy = region.bounds
    dx = (maxx - minx) / grid_size
    dy = (maxy - miny) / grid_size

    task_points = []

    for i in range(grid_size):
        for j in range(grid_size):
            x = minx + (i + 0.5) * dx
            y = miny + (j + 0.5) * dy
            point = Point(x, y)

            # 检查点是否在区域内
            if region.contains(point) or region.buffer(-1e-9).contains(point):
                task_points.append(TaskPoint(x=x, y=y, priority=1.0))

    return task_points


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("目标函数评估模块测试")
    print("=" * 60)

    # 创建测试配置
    radar_config = RadarConfig(P0=0.95, P_min=0.8, beta=0.01, is_air=True)

    # 测试探测概率计算
    print("\n1. 探测概率计算:")
    radar_pos = (0.0, 0.0)
    target_pos = (10.0, 0.0)
    P_detect = calculate_reception_probability(radar_pos, target_pos, radar_config)
    print(f"   雷达位置: {radar_pos}, 目标位置: {target_pos}")
    print(f"   距离: 10.0, 探测概率: {P_detect:.4f}")

    # 测试干扰功率计算
    print("\n2. 干扰功率密度计算:")
    jammer_pos = (0.0, 0.0)
    J = calculate_jamming_power(jammer_pos, target_pos, radar_config)
    print(f"   干扰源位置: {jammer_pos}, 目标位置: {target_pos}")
    print(f"   干扰功率密度: {J:.6f}")

    # 测试二进制解码
    print("\n3. 二进制解码:")
    binary_code = np.array([0, 1, 1])  # 二进制 "011" = 3
    poly_idx = binary_to_polygon_index(binary_code)
    print(f"   二进制编码: {binary_code} -> 多边形索引: {poly_idx}")

    # 测试任务点生成
    print("\n4. 任务点生成:")
    from shapely.geometry import Polygon as ShapelyPolygon
    region = ShapelyPolygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    task_points = generate_uniform_task_points(region, grid_size=5)
    print(f"   区域: 100x100, 网格: 5x5")
    print(f"   生成任务点数量: {len(task_points)}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


def generate_boundary_task_points(
    region: Polygon,
    grid_size: int = 10,
    boundary_width: float = None
) -> List[TaskPoint]:
    """
    在区域边界处生成任务点（用于计算边界覆盖率）

    Args:
        region: 区域多边形
        grid_size: 网格密度
        boundary_width: 边界宽度（默认为区域短边的5%）

    Returns:
        边界任务点列表
    """
    minx, miny, maxx, maxy = region.bounds
    width = maxx - minx
    height = maxy - miny

    if boundary_width is None:
        boundary_width = min(width, height) * 0.05

    task_points = []
    dx = width / grid_size
    dy = height / grid_size

    for i in range(grid_size):
        for j in range(grid_size):
            x = minx + (i + 0.5) * dx
            y = miny + (j + 0.5) * dy
            point = Point(x, y)

            if not (region.contains(point) or region.buffer(-1e-9).contains(point)):
                continue

            boundary_dist = region.exterior.distance(point)
            if boundary_dist <= boundary_width:
                task_points.append(TaskPoint(x=x, y=y, priority=1.0))

    return task_points


def calculate_boundary_ecr(
    radar_positions: np.ndarray,
    boundary_task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: Optional[List[Polygon]] = None,
    binary_codes: Optional[np.ndarray] = None,
    continuous_coords: Optional[np.ndarray] = None
) -> float:
    """
    计算边界ECR（边界覆盖率）

    与calculate_ecr相同，但专门用于计算边界区域

    Args:
        radar_positions: 雷达物理位置
        boundary_task_points: 边界任务点列表
        radar_configs: 雷达配置列表
        convex_polygons: 凸多边形列表
        binary_codes: 二进制编码
        continuous_coords: 连续坐标

    Returns:
        边界ECR ∈ [0, 1]
    """
    return calculate_ecr(
        radar_positions, boundary_task_points, radar_configs,
        convex_polygons, binary_codes, continuous_coords
    )


def normalize_jamming_power(J_min: float, J_max: float = 1.0) -> float:
    """
    归一化干扰功率密度到[0,1]范围

    使用非线性变换使目标函数尺度可比

    Args:
        J_min: 最小干扰功率密度
        J_max: 参考最大干扰功率密度（用于归一化）

    Returns:
        归一化后的值 ∈ [0, 1]
    """
    if J_min < 1e-10:
        return 1.0  # 最小干扰功率密度为0时，惩罚最大
    # 非线性变换：使较小的J_min变化也能被感知
    normalized = J_min / (J_min + J_max)
    return normalized


def evaluate_deployment_normalized(
    Phi: np.ndarray,
    task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: List[Polygon],
    J: int,
    N_bin: int,
    J_max_ref: float = 0.01  # 参考最大干扰功率
) -> np.ndarray:
    """
    综合评估函数（归一化版本）

    改进点：
    1. 对干扰功率密度进行归一化
    2. 引入尺度因子使两个目标可比
    3. 增加扰动以产生更多Pareto解

    Args:
        Phi: 决策变量矩阵 (J, 2+N_bin)
        task_points: 任务点列表
        radar_configs: 雷达/干扰源配置
        convex_polygons: 凸多边形列表
        J: 雷达数量
        N_bin: 编码位数
        J_max_ref: 参考最大干扰功率

    Returns:
        objectives: [1-ECR, J_norm] 形状 (2,)
    """
    # 提取连续坐标和二进制编码
    continuous = Phi[:, :2].flatten()
    binary = Phi[:, 2:2+N_bin]

    # 解码得到物理位置
    positions = decode_particle(continuous, binary, J, N_bin, convex_polygons)
    positions_array = np.array(positions)

    # 计算ECR（感知效能）
    ECR = calculate_ecr(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons,
        binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    # 计算最小干扰功率密度（压制效能）
    J_min = calculate_jamming_density(
        positions_array, task_points, radar_configs,
        convex_polygons=convex_polygons,
        binary_codes=binary,
        continuous_coords=continuous.reshape(J, 2)
    )

    # 目标函数（最小化问题）
    f1 = 1 - ECR  # 范围 [0, 1]

    # 归一化f2到相同尺度
    # 使用饱和函数避免极端值
    f2 = J_min / (J_min + J_max_ref + 1e-10)

    return np.array([f1, f2])


def create_normalized_evaluate_function(
    task_points: List[TaskPoint],
    radar_configs: List[RadarConfig],
    convex_polygons: List[Polygon],
    J: int,
    N_bin: int,
    J_max_ref: float = 0.01
) -> Callable:
    """
    创建归一化评估函数的工厂函数
    """
    def evaluate_func(Phi: np.ndarray) -> np.ndarray:
        return evaluate_deployment_normalized(
            Phi, task_points, radar_configs, convex_polygons, J, N_bin, J_max_ref
        )
    return evaluate_func
