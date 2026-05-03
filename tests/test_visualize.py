"""
可视化测试脚本 - 一键生成分解结果图
"""

from shapely.geometry import Polygon, MultiPolygon
from src.decomposition import DeploymentRegionDecomposer
from src.region_visualizer import DecompositionVisualizer, RegionVisualizer
import matplotlib.pyplot as plt


def visualize_single_polygon():
    """可视化单个多边形的分解过程"""
    print("=" * 60)
    print("可视化示例1: 带空洞的多边形")
    print("=" * 60)

    # 创建一个带空洞的凹多边形
    exterior = [(0, 0), (6, 0), (6, 6), (0, 6)]
    hole = [(2, 2), (4, 2), (4, 4), (2, 4)]
    polygon = Polygon(exterior, [hole])

    # 分解
    decomposer = DeploymentRegionDecomposer(verbose=False)
    result = decomposer.decompose(polygon)
    convex_polys, codes, n_bits = result

    print(f"分解完成: {len(convex_polys)} 个凸多边形")

    # 使用集成可视化器
    viz = DecompositionVisualizer(figsize=(14, 10))
    viz.visualize_result(
        original=polygon,
        decomposition_result=result,
        save_path="decomposition_result_1.png",  # 保存图片
        show=True  # 显示图形
    )

    return polygon, result


def visualize_comparison():
    """对比多个多边形的分解结果"""
    print("\n" + "=" * 60)
    print("可视化示例2: 多边形对比")
    print("=" * 60)

    # 准备多个测试多边形
    test_polygons = [
        ("凸多边形", Polygon([(0, 0), (3, 0), (3, 3), (0, 3)])),

        ("凹多边形", Polygon([
            (0, 0), (4, 0), (4, 1), (1, 1),
            (1, 4), (0, 4)
        ])),

        ("带空洞", Polygon(
            [(0, 0), (5, 0), (5, 5), (0, 5)],
            [[(2, 2), (3, 2), (3, 3), (2, 3)]]
        )),
    ]

    # 分解器
    decomposer = DeploymentRegionDecomposer(verbose=False)

    # 对比可视化
    viz = DecompositionVisualizer(figsize=(15, 5))
    viz.visualize_comparison(
        polygons=test_polygons,
        decomposer=decomposer,
        save_path="comparison_result.png",
        show=True
    )


def visualize_step_by_step():
    """分步可视化分解过程"""
    print("\n" + "=" * 60)
    print("可视化示例3: 分步分解过程")
    print("=" * 60)

    from region_decomposition import (
        decompose_connected_components,
        eliminate_holes,
        convex_decomposition
    )

    # 创建一个复杂多边形
    exterior = [(0, 0), (8, 0), (8, 8), (0, 8)]
    hole1 = [(1, 1), (3, 1), (3, 3), (1, 3)]
    hole2 = [(5, 5), (7, 5), (7, 7), (5, 7)]
    polygon = Polygon(exterior, [hole1, hole2])

    print("执行分步分解...")

    # 获取中间步骤结果
    components = decompose_connected_components(polygon)
    hole_free = []
    for comp in components:
        hole_free.extend(eliminate_holes(comp))

    convex_parts = []
    for poly in hole_free:
        convex_parts.extend(convex_decomposition(poly))

    # 使用基础可视化器
    visualizer = RegionVisualizer(figsize=(14, 10))

    # 创建分步结果字典
    step_results = {
        'original': polygon,
        'connected_components': components,
        'hole_free': hole_free,
        'convex_parts': convex_parts
    }

    # 绘制分步过程
    visualizer.plot_step_by_step(
        step_results=step_results,
        save_path="step_by_step.png"
    )

    print("分步可视化完成!")


def visualize_custom_polygon():
    """可视化自定义多边形 - 在这里修改你的多边形"""
    print("\n" + "=" * 60)
    print("可视化示例4: 自定义多边形")
    print("=" * 60)

    # ===========================================
    # 在这里定义你自己的多边形！
    # ===========================================

    # 示例：创建一个星形多边形
    import numpy as np

    # 星形参数
    n_points = 8  # 星形的点数
    outer_radius = 5
    inner_radius = 2

    angles = np.linspace(0, 2*np.pi, 2*n_points, endpoint=False)
    coords = []
    for i, angle in enumerate(angles):
        r = outer_radius if i % 2 == 0 else inner_radius
        x = r * np.cos(angle)
        y = r * np.sin(angle)
        coords.append((x, y))

    my_polygon = Polygon(coords)

    # ===========================================

    # 分解
    decomposer = DeploymentRegionDecomposer(verbose=True)
    result = decomposer.decompose(my_polygon)

    # 可视化
    viz = DecompositionVisualizer(figsize=(14, 10))
    viz.visualize_result(
        original=my_polygon,
        decomposition_result=result,
        save_path="custom_polygon.png",
        show=True
    )

    return my_polygon, result


if __name__ == "__main__":
    import sys

    print("部署区域分解 - 可视化测试")
    print("=" * 60)
    print("\n可用示例:")
    print("  1 - 单个多边形分解")
    print("  2 - 多边形对比")
    print("  3 - 分步分解过程")
    print("  4 - 自定义多边形（可修改代码）")
    print("  all - 运行所有示例")
    print()

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("请选择 (1/2/3/4/all): ").strip()

    if choice == "1":
        visualize_single_polygon()
    elif choice == "2":
        visualize_comparison()
    elif choice == "3":
        visualize_step_by_step()
    elif choice == "4":
        visualize_custom_polygon()
    elif choice == "all":
        visualize_single_polygon()
        visualize_comparison()
        visualize_step_by_step()
        visualize_custom_polygon()
    else:
        print("无效选择，运行默认示例(1)")
        visualize_single_polygon()

    print("\n" + "=" * 60)
    print("可视化完成！图片已保存到当前目录。")
    print("=" * 60)
