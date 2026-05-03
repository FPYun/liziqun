"""
网格化雷达覆盖评估器

用 numpy/CuPy 数组替代 Shapely 几何运算，支持 GPU 加速。
"""

import numpy as np

# CuPy 可选导入
CP_AVAILABLE = False
try:
    import cupy as cp
    CP_AVAILABLE = True
except ImportError:
    cp = None


class GridEvaluator:
    """
    网格化雷达覆盖评估器

    将部署区域离散化为 2D 网格，用数组运算计算覆盖率和干扰。
    """

    def __init__(self, width=500, height=500, grid_resolution=1.0,
                 radar_range=50.0, use_gpu=False):
        """
        参数:
            width, height: 区域尺寸 (km)
            grid_resolution: 网格分辨率 (km/格)
            radar_range: 雷达探测半径 (km)
            use_gpu: 是否使用 CuPy GPU 加速
        """
        self.width = width
        self.height = height
        self.grid_resolution = grid_resolution
        self.radar_range = radar_range

        self.nx = int(width / grid_resolution)
        self.ny = int(height / grid_resolution)
        self.total_pixels = self.nx * self.ny

        self.use_gpu = use_gpu and CP_AVAILABLE
        self.xp = cp if self.use_gpu else np

        # 预计算网格坐标 (中心点)
        x_coords = np.arange(grid_resolution / 2, width, grid_resolution)
        y_coords = np.arange(grid_resolution / 2, height, grid_resolution)
        self.xx, self.yy = np.meshgrid(x_coords, y_coords)  # shape: (ny, nx)

        # 预计算雷达覆盖圆的模板 mask
        r_pixels = int(radar_range / grid_resolution)
        template_size = 2 * r_pixels + 1
        ty, tx = np.ogrid[-r_pixels:r_pixels + 1, -r_pixels:r_pixels + 1]
        self.circle_template = (tx * tx + ty * ty) <= r_pixels * r_pixels

        # 预计算圆形模板的有效像素数
        self.circle_pixels = np.sum(self.circle_template)

        # GPU 优化：预加载模板到 GPU（消除 per-radar cp.array() 拷贝）
        self.cp_circle_template = cp.array(self.circle_template) if self.use_gpu else None

        # 预计算压制干扰内核 (float32, 连续衰减)
        # power = 1 / (1 + d² / R²), d = 像素距离, R = 雷达半径像素数
        r_sq = r_pixels * r_pixels
        self.jam_kernel = (1.0 / (1.0 + (tx.astype(np.float32)**2 + ty.astype(np.float32)**2) / r_sq)).astype(np.float32)
        self.cp_jam_kernel = cp.array(self.jam_kernel) if self.use_gpu else None

    def get_config(self):
        return {
            'width': self.width,
            'height': self.height,
            'grid_resolution': self.grid_resolution,
            'radar_range': self.radar_range,
            'nx': self.nx,
            'ny': self.ny,
            'total_pixels': self.total_pixels,
            'use_gpu': self.use_gpu,
            'circle_pixels': int(self.circle_pixels),
        }

    def _place_radar_mask(self, cx, cy):
        """在网格上放置单台雷达的覆盖 mask (numpy)"""
        mask = np.zeros((self.ny, self.nx), dtype=bool)

        # 雷达圆心在网格中的像素坐标
        px = int(cx / self.grid_resolution)
        py = int(cy / self.grid_resolution)

        r_pixels = int(self.radar_range / self.grid_resolution)

        # 计算 mask 在网格中的放置范围
        x_start = max(0, px - r_pixels)
        x_end = min(self.nx, px + r_pixels + 1)
        y_start = max(0, py - r_pixels)
        y_end = min(self.ny, py + r_pixels + 1)

        if x_start >= x_end or y_start >= y_end:
            return mask

        # 计算模板中对应的范围
        tx_start = x_start - (px - r_pixels)
        tx_end = tx_start + (x_end - x_start)
        ty_start = y_start - (py - r_pixels)
        ty_end = ty_start + (y_end - y_start)

        mask[y_start:y_end, x_start:x_end] = self.circle_template[ty_start:ty_end, tx_start:tx_end]
        return mask

    def _place_radar_mask_batch(self, positions):
        """批量放置多台雷达的覆盖 mask (向量化 numpy)"""
        # positions: (N, 2) 物理坐标
        masks = np.zeros((positions.shape[0], self.ny, self.nx), dtype=bool)
        for i, (cx, cy) in enumerate(positions):
            masks[i] = self._place_radar_mask(cx, cy)
        return masks

    def compute_coverage(self, physical_positions_np):
        """
        计算覆盖率（纯 numpy，支持批量）

        physical_positions_np: (N, 2) numpy 数组，物理坐标 (km)
        返回: 覆盖率 [0, 1]
        """
        n_radars = physical_positions_np.shape[0]

        # 逐个放置雷达 mask 并合并
        union_mask = np.zeros((self.ny, self.nx), dtype=bool)
        for i in range(n_radars):
            cx, cy = physical_positions_np[i]
            mask = self._place_radar_mask(cx, cy)
            union_mask = union_mask | mask

        coverage = np.sum(union_mask) / self.total_pixels
        return coverage

    def compute_coverage_gpu(self, physical_positions_np):
        """
        计算覆盖率（CuPy GPU 加速版本）

        physical_positions_np: (N, 2) numpy 数组
        返回: 覆盖率 [0, 1]
        """
        if not self.use_gpu:
            return self.compute_coverage(physical_positions_np)

        n_radars = physical_positions_np.shape[0]
        r_pixels = int(self.radar_range / self.grid_resolution)

        # 转换为 GPU 像素坐标
        px = (physical_positions_np[:, 0] / self.grid_resolution).astype(np.int32)
        py = (physical_positions_np[:, 1] / self.grid_resolution).astype(np.int32)

        # 在 GPU 上创建网格，逐个叠加圆形
        # 使用位运算 OR 来合并
        union = cp.zeros((self.ny, self.nx), dtype=cp.bool_)

        for i in range(n_radars):
            cx, cy = px[i], py[i]
            x_start = max(0, cx - r_pixels)
            x_end = min(self.nx, cx + r_pixels + 1)
            y_start = max(0, cy - r_pixels)
            y_end = min(self.ny, cy + r_pixels + 1)

            if x_start >= x_end or y_start >= y_end:
                continue

            tx_start = x_start - (cx - r_pixels)
            tx_end = tx_start + (x_end - x_start)
            ty_start = y_start - (cy - r_pixels)
            ty_end = ty_start + (y_end - y_start)

            patch = cp.array(self.circle_template[ty_start:ty_end, tx_start:tx_end])
            union[y_start:y_end, x_start:x_end] = cp.logical_or(
                union[y_start:y_end, x_start:x_end], patch
            )

        coverage = float(cp.sum(union)) / self.total_pixels
        return coverage

    def compute_coverage_gpu_v2(self, physical_positions_np):
        """
        计算覆盖率（GPU 优化版：模板预加载，消除 per-radar 拷贝）

        与旧版区别：circle_template 在 __init__ 中已预加载为 CuPy 数组，
        不再每次评估都做 cp.array() 拷贝。
        """
        if not self.use_gpu:
            return self.compute_coverage(physical_positions_np)

        n_radars = physical_positions_np.shape[0]
        r_pixels = int(self.radar_range / self.grid_resolution)

        # 所有雷达坐标一次性转 GPU
        px = cp.asarray(
            (physical_positions_np[:, 0] / self.grid_resolution).astype(np.int32))
        py = cp.asarray(
            (physical_positions_np[:, 1] / self.grid_resolution).astype(np.int32))

        # 在 GPU 上用 scatter_add 累加覆盖计数
        acc = cp.zeros((self.ny, self.nx), dtype=cp.int32)
        template = self.cp_circle_template  # 已在 GPU 上

        for i in range(n_radars):
            cx, cy = int(px[i]), int(py[i])
            x_start = max(0, cx - r_pixels)
            x_end = min(self.nx, cx + r_pixels + 1)
            y_start = max(0, cy - r_pixels)
            y_end = min(self.ny, cy + r_pixels + 1)

            if x_start >= x_end or y_start >= y_end:
                continue

            tx_start = x_start - (cx - r_pixels)
            tx_end = tx_start + (x_end - x_start)
            ty_start = y_start - (cy - r_pixels)
            ty_end = ty_start + (y_end - y_start)

            # 直接使用 GPU 上的模板，无需 cp.array() 拷贝
            acc[y_start:y_end, x_start:x_end] += template[ty_start:ty_end, tx_start:tx_end]

        coverage = float(cp.sum(acc > 0)) / self.total_pixels
        return coverage

    def compute_interference(self, physical_positions_np):
        """
        计算对区域目标的平均压制干扰功率 (纯 numpy)

        模型：每台雷达对区域发射压制信号，功率随距离衰减 P(d) = 1/(1+d²/R²)。
        对每个网格像素累加所有雷达的压制功率，返回区域平均功率密度。
        """
        n = physical_positions_np.shape[0]
        if n == 0:
            return 0.0

        r_pixels = int(self.radar_range / self.grid_resolution)
        acc = np.zeros((self.ny, self.nx), dtype=np.float32)

        for i in range(n):
            cx, cy = physical_positions_np[i]
            px = int(cx / self.grid_resolution)
            py = int(cy / self.grid_resolution)

            x_start = max(0, px - r_pixels)
            x_end = min(self.nx, px + r_pixels + 1)
            y_start = max(0, py - r_pixels)
            y_end = min(self.ny, py + r_pixels + 1)

            if x_start >= x_end or y_start >= y_end:
                continue

            tx_start = x_start - (px - r_pixels)
            tx_end = tx_start + (x_end - x_start)
            ty_start = y_start - (py - r_pixels)
            ty_end = ty_start + (y_end - y_start)

            acc[y_start:y_end, x_start:x_end] += self.jam_kernel[ty_start:ty_end, tx_start:tx_end]

        return float(np.mean(acc))

    def compute_interference_gpu(self, physical_positions_np):
        """
        计算对区域目标的平均压制干扰功率 (GPU 加速)

        与 compute_coverage_gpu_v2 策略一致：jam_kernel 在 __init__ 中预加载到 GPU。
        """
        if not self.use_gpu:
            return self.compute_interference(physical_positions_np)

        n = physical_positions_np.shape[0]
        if n == 0:
            return 0.0

        r_pixels = int(self.radar_range / self.grid_resolution)

        px = cp.asarray(
            (physical_positions_np[:, 0] / self.grid_resolution).astype(np.int32))
        py = cp.asarray(
            (physical_positions_np[:, 1] / self.grid_resolution).astype(np.int32))

        acc = cp.zeros((self.ny, self.nx), dtype=cp.float32)
        kernel = self.cp_jam_kernel

        for i in range(n):
            cx, cy = int(px[i]), int(py[i])
            x_start = max(0, cx - r_pixels)
            x_end = min(self.nx, cx + r_pixels + 1)
            y_start = max(0, cy - r_pixels)
            y_end = min(self.ny, cy + r_pixels + 1)

            if x_start >= x_end or y_start >= y_end:
                continue

            tx_start = x_start - (cx - r_pixels)
            tx_end = tx_start + (x_end - x_start)
            ty_start = y_start - (cy - r_pixels)
            ty_end = ty_start + (y_end - y_start)

            acc[y_start:y_end, x_start:x_end] += kernel[ty_start:ty_end, tx_start:tx_end]

        return float(cp.mean(acc))

    def evaluate(self, normalized_coords):
        """
        完整的单次评估

        normalized_coords: (J, D) 归一化坐标矩阵 + 二进制变量
        返回: np.array([coverage, interference])
        """
        # 将归一化坐标转换为物理坐标 [0,1] → [0, width/height]
        phys_x = normalized_coords[:, 0] * self.width
        phys_y = normalized_coords[:, 1] * self.height
        phys = np.column_stack([phys_x, phys_y])

        if self.use_gpu:
            coverage = self.compute_coverage_gpu_v2(phys)
            interference = self.compute_interference_gpu(phys)
        else:
            coverage = self.compute_coverage(phys)
            interference = self.compute_interference(phys)
        return np.array([coverage, interference])


# 导出一个便捷函数，保持与 MOPSO 兼容的接口
def create_evaluator(width=500, height=500, grid_resolution=1.0,
                     radar_range=50.0, use_gpu=False):
    """创建网格评估器并返回 evaluate 函数"""
    evaluator = GridEvaluator(
        width=width, height=height,
        grid_resolution=grid_resolution,
        radar_range=radar_range,
        use_gpu=use_gpu
    )
    return evaluator.evaluate, evaluator
