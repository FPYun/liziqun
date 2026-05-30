"""
可视化区域坐标变换算法流程

展示算法如何将归一化空间 [0,1]×[0,1] 中的坐标
映射到任意凸多边形内的物理坐标。

变换公式（论文算法）：
  x = hat_x * (ub_x - lb_x) + lb_x           (全局x边界)
  y = hat_y * (ub_y(x) - lb_y(x)) + lb_y(x)  (局部y边界，依赖x)

其中 ub_y(x) 和 lb_y(x) 通过垂直扫描线求交计算。
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from shapely.geometry import Polygon, LineString, Point as ShapelyPoint
from src.coordinate_transform import transform_coordinates, get_vertical_intersection_y_bounds

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 创建多种凸多边形形状 ──────────────────────────────────────────
def create_test_polygons():
    """创建多种典型凸多边形"""
    return [
        ("正方形", Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])),
        ("三角形", Polygon([(0, 0), (5, 0), (2.5, 5)])),
        ("平行四边形", Polygon([(0, 0), (4, 1), (6, 4), (2, 3)])),
        ("不规则凸\n五边形", Polygon([(0, 0), (3, 0), (5, 2), (4, 4), (1, 3)])),
    ]


def draw_unit_square_with_grid(ax, grid_size=8):
    """绘制归一化空间 [0,1]×[0,1] 的网格"""
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(-0.08, 1.08)
    ax.set_aspect('equal')

    # 网格点
    points_x, points_y = [], []
    for i in range(grid_size + 1):
        for j in range(grid_size + 1):
            points_x.append(i / grid_size)
            points_y.append(j / grid_size)

    ax.scatter(points_x, points_y, c='#E74C3C', s=12, zorder=5, edgecolors='white', linewidth=0.3)

    # 单位矩形边框
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, edgecolor='#2C3E50', linewidth=2.5, zorder=3))

    # 坐标轴箭头注解
    ax.annotate('', xy=(1.08, 0), xytext=(-0.02, 0),
                arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.5))
    ax.annotate('', xy=(0, 1.08), xytext=(0, -0.02),
                arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=1.5))
    ax.text(1.10, -0.03, r'$\hat{x}$', fontsize=11, ha='center', va='top')
    ax.text(-0.03, 1.10, r'$\hat{y}$', fontsize=11, ha='right', va='center')

    ax.axis('off')


def draw_transformed_grid_in_polygon(ax, polygon, grid_size=8):
    """在凸多边形内绘制变换后的网格"""
    minx, miny, maxx, maxy = polygon.bounds
    margin = max((maxx - minx), (maxy - miny)) * 0.15
    ax.set_xlim(minx - margin, maxx + margin)
    ax.set_ylim(miny - margin, maxy + margin)
    ax.set_aspect('equal')

    # 绘制多边形
    coords = list(polygon.exterior.coords)
    ax.fill([c[0] for c in coords], [c[1] for c in coords],
            alpha=0.15, color='#3498DB', edgecolor='#2C3E50', linewidth=2.5, zorder=2)

    # 计算变换后的网格点
    for i in range(grid_size + 1):
        for j in range(grid_size + 1):
            hat_x = i / grid_size
            hat_y = j / grid_size
            try:
                x, y = transform_coordinates(polygon, hat_x, hat_y)
                ax.scatter(x, y, c='#E74C3C', s=12, zorder=5, edgecolors='white', linewidth=0.3)
            except Exception:
                pass  # 跳过变异常点

    # 标注顶点
    for k, (vx, vy) in enumerate(coords[:-1]):
        ax.scatter(vx, vy, c='#2C3E50', s=50, zorder=6, marker='s')
        ax.annotate(f'V{k}', (vx, vy), textcoords="offset points",
                   xytext=(5, 5), fontsize=7, fontweight='bold')

    ax.axis('off')


# ═══════════════════════════════════════════════════════════════════
# 图1：归一化空间 → 物理空间 对比（4种凸多边形）
# ═══════════════════════════════════════════════════════════════════
def generate_figure1():
    print("生成图1: 归一化空间到物理空间的变换对比...")
    polygons = create_test_polygons()

    fig = plt.figure(figsize=(16, 9))

    # ── 左侧大列：归一化空间（共用一个即可） ──
    ax_unit = fig.add_subplot(2, 4, (1, 5))  # 占左侧两行
    draw_unit_square_with_grid(ax_unit, grid_size=8)
    ax_unit.set_title("归一化空间\n$[0,1] \\times [0,1]$", fontsize=13, fontweight='bold', y=1.01)

    # ── 右侧 4 个子图：不同凸多边形的变换结果 ──
    positions = [2, 3, 6, 7]  # 对应 (1,2), (1,3), (2,2), (2,3) in a 2x4 grid
    for idx, (name, poly) in enumerate(polygons):
        pos = positions[idx]
        ax = fig.add_subplot(2, 4, pos)
        draw_transformed_grid_in_polygon(ax, poly, grid_size=8)
        ax.set_title(f"{name}", fontsize=12, fontweight='bold', y=1.01)

    # 连接箭头：从归一化空间指向物理空间
    fig.text(0.36, 0.52, '===>', fontsize=22, ha='center', va='center',
             fontweight='bold', color='#2C3E50', family='monospace')

    fig.suptitle("坐标变换算法 — 归一化空间到凸多边形物理空间的映射",
                 fontsize=15, fontweight='bold', y=0.99)

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    path = os.path.join(OUTPUT_DIR, 'coordinate_transform_overview.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {path}")
    plt.close()


# ═══════════════════════════════════════════════════════════════════
# 图2：坐标变换的数学步骤详解（垂直线求交法）
# ═══════════════════════════════════════════════════════════════════
def generate_figure2():
    print("生成图2: 坐标变换步骤详解...")

    # 使用平行四边形作为示例（最有代表性）
    polygon = Polygon([(0, 0), (4, 1), (6, 4), (2, 3)])

    # 选取 3 个有代表性的归一化点
    test_points = [
        (0.25, 0.25, "A: 偏左下"),
        (0.60, 0.70, "B: 偏右上"),
        (0.85, 0.15, "C: 偏右下"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    for panel_idx, (hat_x, hat_y, label) in enumerate(test_points):
        ax = axes[panel_idx]

        # ── 绘制多边形 ──
        coords = list(polygon.exterior.coords)
        ax.fill([c[0] for c in coords], [c[1] for c in coords],
                alpha=0.12, color='#3498DB', edgecolor='#2C3E50', linewidth=2.5)

        # ── 步骤1: 根据 hat_x 计算物理 x ──
        minx, _, maxx, _ = polygon.bounds
        phys_x = hat_x * (maxx - minx) + minx

        # 绘制垂直线 x = phys_x
        _, miny, _, maxy = polygon.bounds
        y_extra = (maxy - miny) * 0.3
        ax.axvline(x=phys_x, color='#E74C3C', linewidth=2, linestyle='--', alpha=0.8, zorder=4)

        # ── 步骤2: 计算垂直线与多边形的交点（局部y边界） ──
        lb_y, ub_y = get_vertical_intersection_y_bounds(polygon, phys_x)

        # 绘制交点范围
        ax.plot([phys_x, phys_x], [lb_y, ub_y], color='#27AE60', linewidth=4,
                solid_capstyle='round', zorder=5)
        ax.scatter([phys_x, phys_x], [lb_y, ub_y], c='#27AE60', s=80, zorder=6, edgecolors='white', linewidth=1)

        # 标注上下界
        ax.annotate(f'$l_y$={lb_y:.2f}', (phys_x, lb_y),
                   textcoords="offset points", xytext=(-55, -12),
                   fontsize=9, color='#27AE60', fontweight='bold')
        ax.annotate(f'$u_y$={ub_y:.2f}', (phys_x, ub_y),
                   textcoords="offset points", xytext=(-55, 5),
                   fontsize=9, color='#27AE60', fontweight='bold')

        # ── 步骤3: 根据 hat_y 在局部y范围内计算物理 y ──
        phys_y = hat_y * (ub_y - lb_y) + lb_y

        # 在垂直线段上标注 hat_y 的比例位置
        y_ratio_pos = hat_y * (ub_y - lb_y) + lb_y
        ax.scatter([phys_x], [phys_y], c='#E74C3C', s=150, zorder=7,
                  edgecolors='white', linewidth=2, marker='*')

        # 标注最终点
        ax.annotate(f'({phys_x:.2f}, {phys_y:.2f})', (phys_x, phys_y),
                   textcoords="offset points", xytext=(12, -12),
                   fontsize=10, color='#C0392B', fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                            edgecolor='#C0392B', alpha=0.9))

        # ── 步骤4: 标注全局 x 边界 ──
        ax.axvline(x=minx, color='#95A5A6', linewidth=1, linestyle=':', alpha=0.6)
        ax.axvline(x=maxx, color='#95A5A6', linewidth=1, linestyle=':', alpha=0.6)
        ax.annotate(f'$l_x$={minx}', (minx, miny - y_extra * 0.6),
                   fontsize=8, color='#7F8C8D', ha='center')
        ax.annotate(f'$u_x$={maxx}', (maxx, miny - y_extra * 0.6),
                   fontsize=8, color='#7F8C8D', ha='center')

        # ── 标注顶点 ──
        for k, (vx, vy) in enumerate(coords[:-1]):
            ax.scatter(vx, vy, c='#2C3E50', s=40, zorder=8, marker='s')
            ax.annotate(f'V{k}', (vx, vy), textcoords="offset points",
                       xytext=(4, 4), fontsize=7, fontweight='bold')

        # 设置范围和标题
        margin_x = (maxx - minx) * 0.2
        margin_y = (maxy - miny) * 0.2
        ax.set_xlim(minx - margin_x, maxx + margin_x)
        ax.set_ylim(miny - margin_y, maxy + margin_y)
        ax.set_aspect('equal')

        # 标题包含公式
        ax.set_title(
            f"{label}\n"
            f"$\\hat{{x}}$={hat_x:.2f}, $\\hat{{y}}$={hat_y:.2f}\n"
            f"$x$={phys_x:.2f}, $y$={phys_y:.2f}",
            fontsize=11, fontweight='bold', pad=12
        )

        ax.axis('off')

    fig.suptitle("坐标变换详细步骤 — 垂直线求交法",
                 fontsize=15, fontweight='bold', y=1.01)

    # 底部图例
    legend_elements = [
        mpatches.Patch(facecolor='#3498DB', alpha=0.12, edgecolor='#2C3E50', label='凸多边形区域'),
        plt.Line2D([0], [0], color='#E74C3C', linewidth=2, linestyle='--',
                   label=r'Step 1: $x = \hat{x} \cdot (u_x - l_x) + l_x$'),
        plt.Line2D([0], [0], color='#27AE60', linewidth=3,
                   label=r'Step 2: 垂直扫描线求 $l_y(x), u_y(x)$'),
        plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='#E74C3C', markersize=12,
                   label=r'Step 3: $y = \hat{y} \cdot (u_y - l_y) + l_y$'),
        plt.Line2D([0], [0], color='#95A5A6', linewidth=1, linestyle=':',
                   label=r'全局 x 边界 $l_x, u_x$'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=5, fontsize=9,
               framealpha=0.9, bbox_to_anchor=(0.5, -0.03))

    plt.tight_layout(rect=[0, 0.05, 1, 0.97])

    path = os.path.join(OUTPUT_DIR, 'coordinate_transform_detail.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {path}")
    plt.close()


# ═══════════════════════════════════════════════════════════════════
# 图3：算法在"区域分割→坐标变换→优化"整个流程中的定位
# ═══════════════════════════════════════════════════════════════════
def generate_figure3():
    print("生成图3: 算法在整体流程中的定位...")

    from src.decomposition import DeploymentRegionDecomposer
    from src.evaluation import decode_particle

    # 创建一个 L 形区域并分解
    l_shape = Polygon([
        (0, 0), (8, 0), (8, 2), (2.5, 2),
        (2.5, 6), (0, 6)
    ])
    decomposer = DeploymentRegionDecomposer(verbose=False)
    convex_polys, codes, n_bits = decomposer.decompose(l_shape)

    print(f"  分解为 {len(convex_polys)} 个子区域, {n_bits} 位编码")

    # 模拟单个雷达的坐标为每个子区域生成均匀采样点
    J = 1
    N_bin = n_bits

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # ── Panel 1: 区域分割结果 ──
    ax = axes[0]
    colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C']
    for idx, poly in enumerate(convex_polys):
        color = colors[idx % len(colors)]
        coords = list(poly.exterior.coords)
        ax.fill([c[0] for c in coords], [c[1] for c in coords],
                alpha=0.5, color=color, edgecolor='#2C3E50', linewidth=2)
        c = poly.centroid
        code = codes.get(idx, '')
        ax.text(c.x, c.y, f"S{idx}\n({code})", ha='center', va='center', fontsize=9,
               fontweight='bold', bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))

    ax.set_title("Step 1: 区域分割\n(L形区域→凸多边形+编码)", fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')

    # ── Panel 2: 坐标变换（选一个子区域展示） ──
    ax = axes[1]
    target_poly = convex_polys[2] if len(convex_polys) > 2 else convex_polys[0]
    coords = list(target_poly.exterior.coords)

    ax.fill([c[0] for c in coords], [c[1] for c in coords],
            alpha=0.2, color='#3498DB', edgecolor='#2C3E50', linewidth=2.5)

    # 在子区域内生成网格
    for i in range(7):
        for j in range(7):
            hat_x, hat_y = i / 6, j / 6
            try:
                x, y = transform_coordinates(target_poly, hat_x, hat_y)
                ax.scatter(x, y, c='#E74C3C', s=10, zorder=5, alpha=0.7)
            except Exception:
                pass

    # 标注子区域编码
    idx = convex_polys.index(target_poly)
    code = codes.get(idx, '')
    centroid = target_poly.centroid
    ax.text(centroid.x, centroid.y, f"子区域 {idx}\n编码: {code}",
           ha='center', va='center', fontsize=11, fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='white', edgecolor='#2C3E50', alpha=0.9))

    # 画一条扫描线示例
    mid_x = centroid.x
    lb_y, ub_y = get_vertical_intersection_y_bounds(target_poly, mid_x)
    ax.axvline(x=mid_x, color='#27AE60', linewidth=2, linestyle='--', alpha=0.7)
    ax.plot([mid_x, mid_x], [lb_y, ub_y], color='#27AE60', linewidth=3, solid_capstyle='round')

    ax.set_title("Step 2: 坐标变换\n(归一化坐标→物理坐标)", fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')

    # ── Panel 3: 完整部署方案 ──
    ax = axes[2]

    # 绘制整个区域
    x, y = l_shape.exterior.xy
    ax.fill(x, y, alpha=0.12, color='#95A5A6', edgecolor='#2C3E50', linewidth=2, zorder=1)

    # 为 4 个雷达生成随机合法位置
    np.random.seed(42)
    n_radars = 4
    positions = []
    for r in range(n_radars):
        # 每个雷达选一个子区域
        poly_idx = r % len(convex_polys)
        poly = convex_polys[poly_idx]
        # 随机归一化坐标
        for attempt in range(100):
            hat_x, hat_y = np.random.random(), np.random.random()
            try:
                px, py = transform_coordinates(poly, hat_x, hat_y)
                positions.append((px, py, poly_idx))
                break
            except Exception:
                continue

    # 绘制子区域边界
    for idx, poly in enumerate(convex_polys):
        coords = list(poly.exterior.coords)
        ax.plot([c[0] for c in coords], [c[1] for c in coords],
               color='#2C3E50', linewidth=1, linestyle='--', alpha=0.4)

    # 绘制雷达
    for r, (px, py, poly_idx) in enumerate(positions):
        ax.scatter(px, py, c=colors[poly_idx % len(colors)], s=200, zorder=10,
                  edgecolors='#2C3E50', linewidth=2, marker='^')
        ax.annotate(f'R{r+1}', (px, py), textcoords="offset points",
                   xytext=(0, -15), ha='center', fontsize=10, fontweight='bold')

    ax.set_title("Step 3: 部署方案\n(多雷达协同覆盖)", fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')

    fig.suptitle("区域分割 + 坐标变换 + 部署优化 — 算法流程总览",
                 fontsize=15, fontweight='bold', y=1.01)

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    path = os.path.join(OUTPUT_DIR, 'coordinate_transform_pipeline.png')
    plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {path}")
    plt.close()


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("坐标变换算法可视化")
    print("=" * 60)

    generate_figure1()
    generate_figure2()
    generate_figure3()

    print(f"\n完成！共生成 3 张图片，保存在: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
