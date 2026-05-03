"""
生成论文级仿真模型可视化图片

参照参考论文 Section 4.1 "Simulation Model and Parameter Settings"：
- Figure 3 (p.13): 3D 区域分割可视化 — 展示各雷达的覆盖区域
- Figure 4 (p.15): 不同参数设置下的分割模式对比 (2×3 网格)

输出:
- figures/fig3_area_partition_3d.png
- figures/fig4_tessellation_patterns.png
"""

import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union
from dataclasses import dataclass

# 项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import RadarConfig, calculate_reception_probability_radar_eq

# matplotlib 中文配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================================
# 颜色方案
# ============================================================================

# Figure 3: 三个雷达的配色（参照论文）
RADAR_COLORS = ['#F9C80E', '#3185FC', '#E84855']  # 黄、蓝、红
RADAR_COLORS_3D = [
    [0.976, 0.784, 0.055, 0.9],  # 黄
    [0.192, 0.522, 0.988, 0.9],  # 蓝
    [0.910, 0.282, 0.333, 0.9],  # 红
]

# Figure 4: 12 色调色板
PALETTE_12 = [
    '#1B998B', '#FF9B71', '#E84855', '#3185FC',
    '#F9C80E', '#A23B72', '#2E86AB', '#C73E1D',
    '#6A994E', '#BC4749', '#F4A261', '#264653',
]


# ============================================================================
# 区域工厂函数 — 多样化的待处理区域形状
# ============================================================================

def create_simple_rectangle():
    """(a) 简单矩形区域"""
    return Polygon([(0, 0), (300, 0), (300, 300), (0, 300)])


def create_l_shape():
    """(b) L 形区域 — 两个凹顶点"""
    return Polygon([
        (0, 0), (300, 0), (300, 120), (120, 120), (120, 300), (0, 300)
    ])


def create_t_shape():
    """(c) T 形区域 — 两个凹顶点"""
    return Polygon([
        (80, 0), (220, 0), (220, 180), (300, 180), (300, 300), (0, 300), (0, 180), (80, 180)
    ])


def create_cross_shape():
    """(d) 十字形区域 — 四个凹顶点"""
    return Polygon([
        (100, 0), (200, 0), (200, 100), (300, 100), (300, 200),
        (200, 200), (200, 300), (100, 300), (100, 200), (0, 200),
        (0, 100), (100, 100)
    ])


def create_concave_pentagon():
    """(e) 凹五边形 — 一个凹顶点"""
    return Polygon([
        (150, 0), (300, 120), (250, 300), (50, 300), (0, 120)
    ])


def create_region_with_holes():
    """(f) 带空洞的矩形区域"""
    exterior = [(0, 0), (300, 0), (300, 300), (0, 300)]
    hole1 = [(50, 50), (120, 50), (120, 120), (50, 120)]
    hole2 = [(180, 180), (260, 180), (260, 260), (180, 260)]
    return Polygon(exterior, [hole1, hole2])


# ============================================================================
# 雷达位置生成
# ============================================================================

def generate_radar_positions(region, n_radars):
    """在区域内均匀放置雷达（使用区域重心附近的启发式布局）"""
    centroid = region.centroid
    cx, cy = centroid.x, centroid.y

    # 获取区域边界
    minx, miny, maxx, maxy = region.bounds
    rx = (maxx - minx) * 0.35
    ry = (maxy - miny) * 0.35

    positions = []
    for i in range(n_radars):
        angle = 2 * np.pi * i / n_radars + np.pi / 6
        x = cx + rx * np.cos(angle)
        y = cy + ry * np.sin(angle)
        # 确保在区域内
        pt = Point(x, y)
        if not region.contains(pt):
            # 向中心收缩
            for scale in [0.8, 0.6, 0.4, 0.2]:
                x = cx + rx * scale * np.cos(angle)
                y = cy + ry * scale * np.sin(angle)
                if region.contains(Point(x, y)):
                    break
            else:
                x, y = cx, cy
        positions.append((x, y))
    return positions


# ============================================================================
# Figure 3: 3D 区域分割可视化
# ============================================================================

def compute_detection_grid(region, radar_positions, radar_config, grid_size=80):
    """
    在网格上计算各雷达的探测概率（向量化版本，避免数值溢出）

    返回:
        X, Y: 网格坐标
        Z_joint: 联合探测概率 (n_y, n_x)
        dominant: 主导雷达索引 (n_y, n_x)
        mask: 区域内掩码 (n_y, n_x)
    """
    minx, miny, maxx, maxy = region.bounds
    margin = 5
    x = np.linspace(minx - margin, maxx + margin, grid_size)
    y = np.linspace(miny - margin, maxy + margin, grid_size)
    X, Y = np.meshgrid(x, y)

    n_radars = len(radar_positions)

    # 判断哪些点在区域内（向量化）
    mask = np.zeros((grid_size, grid_size), dtype=bool)
    # 使用步长采样加速区域包含判断
    for i in range(grid_size):
        for j in range(grid_size):
            pt = Point(X[i, j], Y[i, j])
            if region.contains(pt) or region.distance(pt) < 2.0:
                mask[i, j] = True

    # 向量化计算各雷达探测概率
    P_detect = np.zeros((grid_size, grid_size, n_radars))
    k_B = 1.38e-23
    T0 = 290.0
    G_linear = 10 ** (radar_config.G_t_dB / 10.0)
    D0_linear = 10 ** (radar_config.D0_dB / 10.0)
    numerator = radar_config.P_t * (G_linear ** 2) * (radar_config.wavelength ** 2) * radar_config.sigma

    for k, (rx, ry) in enumerate(radar_positions):
        # 距离网格 (km)
        d_km = np.sqrt((X - rx) ** 2 + (Y - ry) ** 2)
        # 避免除零：设置最小距离为 1km
        d_km = np.maximum(d_km, 1.0)
        d_m = d_km * 1000.0

        # SNR 计算
        denom = ((4 * np.pi) ** 3) * k_B * T0 * radar_config.bandwidth * (d_m ** 4)
        SNR = numerator / denom

        # 探测概率 P_d = exp(-D0 / (1 + SNR))
        P_d = np.exp(-D0_linear / (1.0 + SNR))
        P_d = np.clip(P_d, 0.0, 1.0)

        # 超出最大探测距离的点置零
        P_d = np.where(d_km > radar_config.R_max, 0.0, P_d)

        # 区域外的点置零
        P_d = np.where(mask, P_d, 0.0)

        P_detect[:, :, k] = P_d

    # 联合探测概率: P_joint = 1 - ∏(1 - P_detect_k)
    P_joint = 1.0 - np.prod(1.0 - P_detect, axis=2)
    P_joint = np.clip(P_joint, 0.0, 1.0)

    # 主导雷达（P_detect 最高的）
    dominant = np.argmax(P_detect, axis=2)

    # 区域外的点设为 NaN
    Z_joint = np.where(mask, P_joint, np.nan)
    dominant_masked = np.where(mask, dominant, -1)

    return X, Y, Z_joint, dominant_masked, mask


def plot_figure_3(save_dir):
    """生成 Figure 3: 3D 区域分割图"""
    print("  生成 Figure 3: 3D 区域分割图...")

    # 创建阶梯形区域
    region = create_l_shape()

    # 分解区域
    decomposer = DeploymentRegionDecomposer(verbose=False)
    convex_polygons, binary_codes, n_bits = decomposer.decompose(region)
    print(f"    区域分解: {len(convex_polygons)} 个凸多边形")

    # 放置 3 个雷达
    radar_positions = generate_radar_positions(region, 3)
    radar_config = RadarConfig(
        P_t=3000.0, G_t_dB=50.0, wavelength=0.3, sigma=0.1,
        bandwidth=15e6, D0_dB=12.5, R_max=60.0,
        jammer_P_t=150.0, jammer_G_t_dB=30.0,
        use_radar_equation=True, P_min=0.8
    )

    # 计算探测概率网格
    grid_size = 80
    X, Y, Z_joint, dominant, mask = compute_detection_grid(
        region, radar_positions, radar_config, grid_size
    )

    # 创建 3D 图
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection='3d')

    # 为每个雷达创建单独的面片，用对应颜色
    for k in range(3):
        Z_k = np.where(dominant == k, Z_joint, np.nan)
        # 透明度
        color = RADAR_COLORS_3D[k]
        ax.plot_surface(
            X, Y, Z_k,
            color=color,
            alpha=0.85,
            linewidth=0,
            antialiased=True,
            shade=True,
        )

    # 绘制分割边界（在 z=0 平面上投影）
    for poly in convex_polygons:
        bx, by = poly.exterior.xy
        ax.plot(bx, by, zs=0, color='black', linewidth=1.2, alpha=0.7)

    # 绘制雷达位置
    for k, (rx, ry) in enumerate(radar_positions):
        ax.scatter([rx], [ry], [0], c='red', s=120, marker='^',
                   edgecolors='black', linewidth=1.5, zorder=10,
                   depthshade=False)
        ax.text(rx, ry, 0.02, f'R{k+1}', fontsize=10, fontweight='bold',
                ha='left', va='bottom')

    # 设置坐标轴
    ax.set_xlabel('X (km)', fontsize=12, labelpad=10)
    ax.set_ylabel('Y (km)', fontsize=12, labelpad=10)
    ax.set_zlabel('Detection Probability', fontsize=12, labelpad=10)
    ax.set_title('3D Area Partitioning for Multi-Radar Network',
                 fontsize=14, fontweight='bold', pad=20)

    # 设置视角
    ax.view_init(elev=30, azim=-60)

    # 添加图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=RADAR_COLORS[0], edgecolor='black', label='Radar 1'),
        Patch(facecolor=RADAR_COLORS[1], edgecolor='black', label='Radar 2'),
        Patch(facecolor=RADAR_COLORS[2], edgecolor='black', label='Radar 3'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=10)

    # 添加参数说明
    param_text = (
        f"Region: L-shape\n"
        f"N = {len(convex_polygons)} sub-regions\n"
        f"Grid: {grid_size}×{grid_size}\n"
        f"R_max = {radar_config.R_max} km"
    )
    ax.text2D(0.82, 0.95, param_text, transform=ax.transAxes,
              fontsize=9, verticalalignment='top',
              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    plt.tight_layout()
    save_path = os.path.join(save_dir, 'fig3_area_partition_3d.png')
    plt.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"    已保存: {save_path}")


# ============================================================================
# Figure 4: 分割模式对比
# ============================================================================

def plot_single_decomposition(ax, region, decomposer, title, show_codes=True):
    """在单个子图上绘制区域的凸分解结果"""
    try:
        convex_polygons, binary_codes, n_bits = decomposer.decompose(region)
    except Exception as e:
        ax.text(0.5, 0.5, f"Decomposition failed:\n{e}",
                ha='center', va='center', transform=ax.transAxes, fontsize=9)
        ax.set_title(title, fontsize=11, fontweight='bold')
        return

    # 先绘制原始区域边界（灰色虚线），作为参考
    if hasattr(region, 'exterior'):
        ox, oy = region.exterior.xy
        ax.plot(ox, oy, color='gray', linewidth=1.0, linestyle='--', alpha=0.5)

    # 绘制每个凸多边形
    for idx, poly in enumerate(convex_polygons):
        color = PALETTE_12[idx % len(PALETTE_12)]
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.6, fc=color, ec='black', linewidth=1.0)

        if show_codes and idx in binary_codes:
            centroid = poly.centroid
            code = binary_codes[idx]
            ax.text(centroid.x, centroid.y, code,
                    ha='center', va='center', fontsize=8, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.85, pad=0.2))

    # 如果原始区域有空洞，用红色虚线标出空洞位置
    if hasattr(region, 'interiors') and len(list(region.interiors)) > 0:
        for interior in region.interiors:
            xi, yi = interior.xy
            ax.fill(xi, yi, alpha=0.9, fc='white', ec='red', linewidth=1.5,
                    linestyle='--')
            hole_poly = Polygon(list(interior.coords))
            hc = hole_poly.centroid
            ax.text(hc.x, hc.y, 'Hole', ha='center', va='center', fontsize=8,
                    color='red', fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='red'))

    ax.set_xlim(-10, 310)
    ax.set_ylim(-10, 310)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.2, linewidth=0.5)

    # 在左下角显示凸多边形数量
    ax.text(0.02, 0.02, f"N = {len(convex_polygons)}",
            transform=ax.transAxes, fontsize=9,
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.6))


def plot_figure_decomposition(save_dir):
    """生成不同待处理区域的分割对比图 (2×3 网格)"""
    print("  生成区域分割对比图...")

    scenarios = [
        ("(a) 简单矩形", create_simple_rectangle()),
        ("(b) L 形区域", create_l_shape()),
        ("(c) T 形区域", create_t_shape()),
        ("(d) 十字形区域", create_cross_shape()),
        ("(e) 凹五边形", create_concave_pentagon()),
        ("(f) 带空洞区域", create_region_with_holes()),
    ]

    decomposer = DeploymentRegionDecomposer(verbose=False)

    fig, axes = plt.subplots(2, 3, figsize=(15, 11))

    for idx, (title, region) in enumerate(scenarios):
        row, col = idx // 3, idx % 3
        ax = axes[row, col]
        plot_single_decomposition(ax, region, decomposer, title)

    fig.suptitle('Deployment Region Decomposition for Different Region Shapes',
                 fontsize=15, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    save_path = os.path.join(save_dir, 'fig4_tessellation_patterns.png')
    plt.savefig(save_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"    已保存: {save_path}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 60)
    print("生成论文级仿真模型可视化图片")
    print("=" * 60)

    save_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(save_dir, exist_ok=True)

    # 生成不同区域的分割对比图
    plot_figure_decomposition(save_dir)

    print("\n" + "=" * 60)
    print("所有图片生成完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
