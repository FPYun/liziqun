"""
可视化区域分割算法对不同类型区域的处理效果

生成一张综合大图，展示6种典型区域形状的分解结果
"""
import sys
import os
import io

# 修复 Windows 中文路径下的编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from src.decomposition import DeploymentRegionDecomposer

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 颜色方案
COLOR_ORIGINAL = '#5B9BD5'
COLOR_DECOMPOSED = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD',
                    '#F0B27A', '#82E0AA', '#F1948A', '#85C1E9', '#BB8FCE', '#73C6B6']


def create_test_regions():
    """创建多种典型测试区域"""
    regions = []

    # 1. 凸矩形（简单区域）
    regions.append(("凸矩形\n(trivial)", Polygon([
        (0, 0), (4, 0), (4, 3), (0, 3)
    ])))

    # 2. L形（凹多边形）
    regions.append(("L形凹区域", Polygon([
        (0, 0), (4, 0), (4, 1), (1.2, 1),
        (1.2, 3), (0, 3)
    ])))

    # 3. T形（凹多边形）
    regions.append(("T形凹区域", Polygon([
        (0, 2), (4, 2), (4, 3), (2.5, 3),
        (2.5, 4), (1.5, 4), (1.5, 3), (0, 3)
    ])))

    # 4. 带空洞的矩形
    regions.append(("带矩形空洞", Polygon(
        [(0, 0), (5, 0), (5, 4), (0, 4)],
        [[(1.5, 1), (3.5, 1), (3.5, 2.5), (1.5, 2.5)]]
    )))

    # 5. 十字形（凹多边形）
    regions.append(("十字形区域", Polygon([
        (1, 0), (2, 0), (2, 1), (3, 1), (3, 2),
        (2, 2), (2, 3), (1, 3), (1, 2), (0, 2), (0, 1), (1, 1)
    ])))

    # 6. 不连通区域（两个分离的矩形）
    regions.append(("不连通区域\n(两块)", MultiPolygon([
        Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
        Polygon([(3, 1.5), (5.5, 1.5), (5.5, 3.5), (3, 3.5)])
    ])))

    # 7. 带双空洞
    regions.append(("带双空洞", Polygon(
        [(0, 0), (6, 0), (6, 5), (0, 5)],
        [[(0.8, 0.8), (2.2, 0.8), (2.2, 2.2), (0.8, 2.2)],
         [(3.5, 2.5), (5, 2.5), (5, 4.2), (3.5, 4.2)]]
    )))

    # 8. 锯齿形（复杂凹多边形）
    regions.append(("锯齿形区域", Polygon([
        (0, 0), (5, 0), (5, 1), (1.5, 1),
        (1.5, 2), (4, 2), (4, 3), (2, 3),
        (2, 4), (3.5, 4), (3.5, 5), (0, 5)
    ])))

    return regions


def plot_single_decomposition(ax_orig, ax_decomp, polygon, name, decomposer):
    """在给定的两个轴上绘制原始区域和分解结果"""
    # 左图：原始区域
    if isinstance(polygon, MultiPolygon):
        for geom in polygon.geoms:
            x, y = geom.exterior.xy
            ax_orig.fill(x, y, alpha=0.6, color=COLOR_ORIGINAL, edgecolor='#2C3E50', linewidth=1.5)
            for interior in geom.interiors:
                xi, yi = interior.xy
                ax_orig.fill(xi, yi, alpha=1.0, color='white', edgecolor='#2C3E50', linewidth=1)
    else:
        x, y = polygon.exterior.xy
        ax_orig.fill(x, y, alpha=0.6, color=COLOR_ORIGINAL, edgecolor='#2C3E50', linewidth=1.5)
        for interior in polygon.interiors:
            xi, yi = interior.xy
            ax_orig.fill(xi, yi, alpha=1.0, color='white', edgecolor='#2C3E50', linewidth=1)
    ax_orig.set_title(name, fontsize=10, fontweight='bold')
    ax_orig.set_aspect('equal')
    ax_orig.axis('off')
    ax_orig.set_xlim(auto=True)
    ax_orig.set_ylim(auto=True)

    # 右图：分解结果
    try:
        convex_polys, codes, n_bits = decomposer.decompose(polygon)
        n_parts = len(convex_polys)

        for idx, poly in enumerate(convex_polys):
            color = COLOR_DECOMPOSED[idx % len(COLOR_DECOMPOSED)]
            x, y = poly.exterior.xy
            ax_decomp.fill(x, y, alpha=0.7, color=color, edgecolor='#2C3E50', linewidth=1)

            # 标注编码
            if idx in codes and codes[idx]:
                centroid = poly.centroid
                ax_decomp.text(centroid.x, centroid.y, codes[idx],
                              ha='center', va='center', fontsize=7,
                              fontweight='bold',
                              bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                       edgecolor='gray', alpha=0.85))

        info = f"{n_parts}个子区域, {n_bits}位编码"
    except Exception as e:
        ax_decomp.text(0.5, 0.5, f"分解失败:\n{str(e)[:80]}",
                      ha='center', va='center', fontsize=7, color='red',
                      transform=ax_decomp.transAxes)
        info = "失败"

    ax_decomp.set_title(info, fontsize=9, color='#2C3E50')
    ax_decomp.set_aspect('equal')
    ax_decomp.axis('off')


def main():
    print("=" * 60)
    print("区域分割算法可视化")
    print("=" * 60)

    decomposer = DeploymentRegionDecomposer(verbose=False)
    regions = create_test_regions()

    # 4行 x 4列 (8个区域，每个占左原图+右分解)
    n = len(regions)  # 8
    fig, axes = plt.subplots(n, 2, figsize=(12, 3.2 * n))

    for i, (name, polygon) in enumerate(regions):
        print(f"[{i+1}/{n}] 处理: {name.replace(chr(10), ' ')}")
        plot_single_decomposition(axes[i, 0], axes[i, 1], polygon, name, decomposer)

    # 列标题
    axes[0, 0].set_title("原始区域\n(Original Region)", fontsize=12, fontweight='bold', y=1.05)
    axes[0, 1].set_title("凸分解结果\n(Convex Decomposition)", fontsize=12, fontweight='bold', y=1.05)

    fig.suptitle("部署区域分解算法 - 多种区域形状对比",
                 fontsize=16, fontweight='bold', y=0.995)

    plt.tight_layout(rect=[0, 0, 1, 0.99])

    save_path = os.path.join(os.path.dirname(__file__), 'decomposition_variety.png')
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"\n图片已保存: {save_path}")
    plt.close()

    # ================================================================
    # 图2：带空洞区域的分解流程详情（4步展示）
    # ================================================================
    print("\n生成分解流程图...")
    polygon_with_hole = Polygon(
        [(0, 0), (5, 0), (5, 4), (0, 4)],
        [[(1.5, 1), (3.5, 1), (3.5, 2.5), (1.5, 2.5)]]
    )

    from src.decomposition import (
        decompose_connected_components, eliminate_holes,
        convex_decomposition, assign_binary_codes
    )

    # 用完整的 decomposer 获取精确的中间结果
    full_decomposer = DeploymentRegionDecomposer(verbose=False)

    fig2, axes2 = plt.subplots(1, 4, figsize=(18, 4.5))

    # Step 1: 原始区域（带空洞）
    ax = axes2[0]
    x, y = polygon_with_hole.exterior.xy
    ax.fill(x, y, alpha=0.5, color=COLOR_ORIGINAL, edgecolor='#2C3E50', linewidth=2)
    for interior in polygon_with_hole.interiors:
        xi, yi = interior.xy
        ax.fill(xi, yi, alpha=1.0, color='white', edgecolor='#E74C3C', linewidth=2, linestyle='--')
    ax.set_title("Step 1: 原始区域（带空洞）\n面积={:.1f}, 空洞={}个".format(
        polygon_with_hole.area, len(polygon_with_hole.interiors)), fontsize=11, fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')

    # Step 2: 连通分量分解
    ax = axes2[1]
    components = decompose_connected_components(polygon_with_hole)
    for idx, comp in enumerate(components):
        color = COLOR_DECOMPOSED[idx]
        x, y = comp.exterior.xy
        ax.fill(x, y, alpha=0.6, color=color, edgecolor='#2C3E50', linewidth=1.5)
        for interior in comp.interiors:
            xi, yi = interior.xy
            ax.fill(xi, yi, alpha=1.0, color='white', edgecolor='#E74C3C', linewidth=1, linestyle='--')
    ax.set_title("Step 2: 连通分量分解\n({}个连通分量)".format(len(components)), fontsize=11, fontweight='bold')
    ax.set_aspect('equal')
    ax.axis('off')

    # Step 3: 消除空洞（对每个连通分量分别处理）
    ax = axes2[2]
    try:
        hole_free_all = []
        for comp in components:
            hole_free = eliminate_holes(comp)
            hole_free_all.extend(hole_free)
        for idx, poly in enumerate(hole_free_all):
            color = COLOR_DECOMPOSED[idx % len(COLOR_DECOMPOSED)]
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.6, color=color, edgecolor='#2C3E50', linewidth=1.5)
        ax.set_title("Step 3: 消除空洞\n切割为{}个无洞多边形".format(len(hole_free_all)), fontsize=11, fontweight='bold')
    except Exception as e:
        ax.text(0.5, 0.5, "失败: {}".format(str(e)[:100]), ha='center', va='center',
               fontsize=7, color='red', transform=ax.transAxes)
        hole_free_all = components
        ax.set_title("Step 3: 消除空洞\n(跳过)", fontsize=11)
    ax.set_aspect('equal')
    ax.axis('off')

    # Step 4: 凸分解 + 二进制编码
    ax = axes2[3]
    try:
        conv_polys_all = []
        for poly in hole_free_all:
            conv_polys = convex_decomposition(poly)
            conv_polys_all.extend(conv_polys)
        codes, n_bits = assign_binary_codes(conv_polys_all)
        for idx, poly in enumerate(conv_polys_all):
            color = COLOR_DECOMPOSED[idx % len(COLOR_DECOMPOSED)]
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.7, color=color, edgecolor='#2C3E50', linewidth=1.5)
            if idx in codes and codes[idx]:
                c = poly.centroid
                ax.text(c.x, c.y, codes[idx], ha='center', va='center', fontsize=9,
                       fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                edgecolor='gray', alpha=0.85))
        ax.set_title("Step 4: 凸分解 + 编码\n({}个子区域, {}位编码)".format(
            len(conv_polys_all), n_bits), fontsize=11, fontweight='bold')
    except Exception as e:
        ax.text(0.5, 0.5, "失败: {}".format(str(e)[:100]), ha='center', va='center',
               fontsize=7, color='red', transform=ax.transAxes)
    ax.set_aspect('equal')
    ax.axis('off')

    fig2.suptitle("区域分割算法流程 — 带空洞矩形示例", fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    save_path2 = os.path.join(os.path.dirname(__file__), 'decomposition_pipeline.png')
    plt.savefig(save_path2, dpi=200, bbox_inches='tight', facecolor='white')
    print("图片已保存: {}".format(save_path2))
    plt.close()

    print("\n完成！共生成 2 张图片。")


if __name__ == "__main__":
    main()
