"""
部署区域分解算法 - 使用示例

本文件提供region_decomposition.py模块的使用示例
"""

from shapely.geometry import Polygon, MultiPolygon
from region_decomposition import (
    DeploymentRegionDecomposer,
    decompose_connected_components,
    eliminate_holes,
    convex_decomposition,
    assign_binary_codes,
    is_polygon_connected,
    validate_polygon
)

# =============================================================================
# 示例1: 基础用法 - 使用DeploymentRegionDecomposer类
# =============================================================================

def example_basic_usage():
    """基础用法示例"""
    print("=" * 60)
    print("示例1: 基础用法")
    print("=" * 60)

    # 创建一个带空洞的凹多边形
    exterior = [(0, 0), (5, 0), (5, 5), (0, 5)]  # 外边界
    hole = [(2, 2), (3, 2), (3, 3), (2, 3)]       # 空洞
    polygon = Polygon(exterior, [hole])

    # 创建分解器（verbose=True显示详细过程）
    decomposer = DeploymentRegionDecomposer(verbose=True)

    # 执行分解
    convex_polys, codes, n_bits = decomposer.decompose(polygon)

    # 输出结果
    print(f"\n结果汇总:")
    print(f"  输入多边形面积: {polygon.area}")
    print(f"  凸多边形数量: {len(convex_polys)}")
    print(f"  二进制位数: {n_bits}")
    print(f"  编码映射: {codes}")

    # 验证凸性
    all_convex = all(p.is_convex for p in convex_polys)
    print(f"  所有结果都是凸多边形: {all_convex}")


# =============================================================================
# 示例2: 分步调用 - 逐步执行算法步骤
# =============================================================================

def example_step_by_step():
    """分步调用示例"""
    print("\n" + "=" * 60)
    print("示例2: 分步调用")
    print("=" * 60)

    # 创建一个复杂的多边形（不连通）
    poly1 = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    poly2 = Polygon([(3, 0), (5, 0), (5, 2), (3, 2)])
    complex_region = MultiPolygon([poly1, poly2])

    print(f"输入: MultiPolygon, 包含 {len(complex_region.geoms)} 个多边形")

    # 步骤1: 处理不连通区域
    components = decompose_connected_components(complex_region)
    print(f"步骤1 - 连通分量: {len(components)} 个")

    # 步骤2: 处理空洞
    hole_free_polys = []
    for comp in components:
        result = eliminate_holes(comp)
        hole_free_polys.extend(result)
    print(f"步骤2 - 无空洞多边形: {len(hole_free_polys)} 个")

    # 步骤3: 凸分解
    convex_polys = []
    for poly in hole_free_polys:
        result = convex_decomposition(poly)
        convex_polys.extend(result)
    print(f"步骤3 - 凸多边形: {len(convex_polys)} 个")

    # 步骤4: 分配二进制编码
    codes, n_bits = assign_binary_codes(convex_polys)
    print(f"步骤4 - 二进制编码: {n_bits} 位")
    print(f"  编码: {codes}")


# =============================================================================
# 示例3: 验证多边形
# =============================================================================

def example_validation():
    """多边形验证示例"""
    print("\n" + "=" * 60)
    print("示例3: 多边形验证")
    print("=" * 60)

    # 有效多边形
    valid_poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    print(f"有效多边形验证: {validate_polygon(valid_poly)}")

    # 检查连通性
    print(f"多边形连通性: {is_polygon_connected(valid_poly)}")

    # 带空洞的多边形（仍连通）
    poly_with_hole = Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        [[(1, 1), (2, 1), (2, 2), (1, 2)]]
    )
    print(f"带空洞多边形连通性: {is_polygon_connected(poly_with_hole)}")


# =============================================================================
# 示例4: 处理各种多边形类型
# =============================================================================

def example_various_polygons():
    """各种多边形类型处理示例"""
    print("\n" + "=" * 60)
    print("示例4: 各种多边形类型")
    print("=" * 60)

    decomposer = DeploymentRegionDecomposer(verbose=False)

    test_cases = [
        ("简单凸多边形", Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])),
        ("凹多边形(L形)", Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)])),
        ("星形多边形", Polygon([
            (0, 2), (0.5, 0.5), (2, 2), (0.5, 1), (1.5, 0)
        ])),
    ]

    for name, polygon in test_cases:
        convex_polys, codes, n_bits = decomposer.decompose(polygon)
        print(f"{name:15} -> 凸多边形: {len(convex_polys)}, 位数: {n_bits}")


# =============================================================================
# 示例5: 性能测试
# =============================================================================

def example_performance():
    """性能测试示例"""
    import time
    import numpy as np

    print("\n" + "=" * 60)
    print("示例5: 性能测试")
    print("=" * 60)

    decomposer = DeploymentRegionDecomposer(verbose=False)

    # 测试不同规模的多边形
    sizes = [10, 20, 50, 100]

    for n in sizes:
        # 创建星形多边形
        angles = np.linspace(0, 2*np.pi, n+1)[:-1]
        coords = [(np.cos(a)*5, np.sin(a)*5) for a in angles]
        polygon = Polygon(coords)

        # 测试性能
        start = time.time()
        result = decomposer.decompose(polygon)
        elapsed = time.time() - start

        print(f"顶点数: {n:3d} -> 时间: {elapsed:.4f}s, 凸多边形: {len(result[0])}")


# =============================================================================
# 示例6: 使用可视化（如果matplotlib可用）
# =============================================================================

def example_visualization():
    """可视化示例"""
    try:
        import matplotlib.pyplot as plt
        from visualization import RegionVisualizer
    except ImportError:
        print("\n跳过可视化示例：matplotlib或visualization模块不可用")
        return

    print("\n" + "=" * 60)
    print("示例6: 可视化")
    print("=" * 60)

    from region_decomposition import create_test_polygons

    # 获取测试多边形
    test_cases = create_test_polygons()

    # 选择第一个非简单多边形进行可视化
    decomposer = DeploymentRegionDecomposer(verbose=False)
    name, polygon = test_cases[2]  # 带空洞的多边形

    print(f"可视化: {name}")

    # 执行分解
    convex_polys, codes, n_bits = decomposer.decompose(polygon)

    # 创建可视化器
    visualizer = RegionVisualizer(figsize=(12, 10))

    # 可视化分解过程
    visualizer.plot_convex_decomposition_details(
        convex_polygons=convex_polys,
        binary_codes=codes,
        original_area=polygon.area,
        save_path=None  # 设置为路径可保存图片
    )


# =============================================================================
# 主函数
# =============================================================================

if __name__ == "__main__":
    import sys

    # 运行所有示例
    examples = [
        example_basic_usage,
        example_step_by_step,
        example_validation,
        example_various_polygons,
        example_performance,
        example_visualization,
    ]

    if len(sys.argv) > 1:
        try:
            # 运行指定示例
            idx = int(sys.argv[1])
            if 1 <= idx <= len(examples):
                examples[idx - 1]()
            else:
                print(f"示例编号应在 1-{len(examples)} 之间")
        except ValueError:
            print("用法: python examples.py [示例编号]")
            print(f"可用示例: 1-{len(examples)}")
    else:
        # 运行所有示例
        for example in examples:
            try:
                example()
            except Exception as e:
                print(f"\n示例执行出错: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("所有示例完成!")
    print("=" * 60)
