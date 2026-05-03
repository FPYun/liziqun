"""
凸多边形内的坐标变换算法 (Coordinate Transformation in Convex Polygon)

用于MOPSO等优化算法，将[0,1]×[0,1]归一化空间内的坐标映射到凸多边形内的物理坐标。
"""

from typing import Tuple, List
import numpy as np
from shapely.geometry import Polygon, LineString, MultiLineString, Point


def is_convex_polygon(polygon: Polygon, epsilon: float = 1e-10) -> bool:
    """
    判断多边形是否为凸多边形。

    算法：对于凸多边形，所有连续边向量的叉积应具有相同符号（同向旋转）。

    Args:
        polygon: 多边形对象
        epsilon: 浮点数精度容差

    Returns:
        True如果是凸多边形，False otherwise
    """
    if polygon.is_empty or not polygon.is_valid:
        return False

    # 获取外部边界坐标（不包括最后一个重复点）
    coords = list(polygon.exterior.coords)[:-1]
    n = len(coords)

    if n < 3:
        return False

    if n == 3:
        return True  # 三角形总是凸的

    # 计算连续边向量的叉积符号
    cross_signs = []

    for i in range(n):
        # 当前点、前一个点、后一个点
        p0 = np.array(coords[(i - 1) % n])
        p1 = np.array(coords[i])
        p2 = np.array(coords[(i + 1) % n])

        # 边向量
        v1 = p1 - p0
        v2 = p2 - p1

        # 2D叉积（z分量）
        cross = v1[0] * v2[1] - v1[1] * v2[0]

        if abs(cross) > epsilon:
            cross_signs.append(np.sign(cross))

    if not cross_signs:
        return True  # 所有点共线

    # 所有叉积应具有相同符号
    return all(s == cross_signs[0] for s in cross_signs)


def get_polygon_x_bounds(polygon: Polygon) -> Tuple[float, float]:
    """
    获取多边形在x轴上的全局上下界。

    Args:
        polygon: 凸多边形对象

    Returns:
        (lb_x, ub_x): x轴下界和上界
    """
    minx, _, maxx, _ = polygon.bounds
    return minx, maxx


def get_vertical_intersection_y_bounds(
    polygon: Polygon,
    x: float,
    epsilon: float = 1e-10
) -> Tuple[float, float]:
    """
    获取垂直线x=x与多边形的交点的y值范围（局部上下界）。

    算法步骤：
    1. 构造一条垂直于x轴的线段，y范围足够大以穿透多边形
    2. 求该线段与多边形的交集
    3. 从交点中提取y的最小值和最大值

    Args:
        polygon: 凸多边形对象
        x: 固定的x坐标值
        epsilon: 浮点数精度容差

    Returns:
        (lb_y, ub_y): 在x处的局部y下界和上界

    Raises:
        ValueError: 当垂直线与多边形无交点时
    """
    # 获取多边形的y边界，用于构造足够长的垂直线段
    _, miny, _, maxy = polygon.bounds

    # 构造足够长的垂直线段（确保能穿透多边形）
    # 添加epsilon确保线段足够长
    y_range = maxy - miny
    vertical_line = LineString([
        (x, miny - y_range - epsilon),
        (x, maxy + y_range + epsilon)
    ])

    # 求垂直线与多边形的交集
    intersection = polygon.intersection(vertical_line)

    if intersection.is_empty:
        raise ValueError(f"垂直线 x={x} 与多边形无交点")

    # 从交点中提取y坐标
    y_coords: List[float] = []

    if isinstance(intersection, Point):
        # 交点是单个点（x刚好在顶点处）
        y_coords.append(intersection.y)
    elif isinstance(intersection, LineString):
        # 交点是线段
        coords = list(intersection.coords)
        y_coords.extend([coord[1] for coord in coords])
    elif isinstance(intersection, MultiLineString):
        # 交点是多条线段（罕见，但在浮点精度问题下可能出现）
        for line in intersection.geoms:
            coords = list(line.coords)
            y_coords.extend([coord[1] for coord in coords])
    else:
        # 其他几何类型，尝试提取坐标
        try:
            coords = list(intersection.coords) if hasattr(intersection, 'coords') else []
            y_coords.extend([coord[1] for coord in coords])
        except Exception:
            raise ValueError(f"无法从交点类型 {type(intersection)} 提取y坐标")

    if not y_coords:
        raise ValueError("无法从交点提取y坐标")

    # 添加小量容差处理浮点精度
    lb_y = min(y_coords) - epsilon
    ub_y = max(y_coords) + epsilon

    return lb_y, ub_y


def transform_coordinates(
    polygon: Polygon,
    hat_x: float,
    hat_y: float,
    epsilon: float = 1e-10
) -> Tuple[float, float]:
    """
    将归一化坐标 (hat_x, hat_y) 映射到凸多边形内的物理坐标 (x, y)。

    变换顺序：先x方向，后y方向

    x坐标计算：
        x = hat_x * (ub_x - lb_x) + lb_x

    y坐标计算（局部边界依赖于x）：
        y = hat_y * (ub_y(x) - lb_y(x)) + lb_y(x)

    Args:
        polygon: 凸多边形对象（必须是凸的）
        hat_x: 归一化x变量，范围 [0, 1]
        hat_y: 归一化y变量，范围 [0, 1]
        epsilon: 浮点数精度容差

    Returns:
        (x, y): 映射后的物理坐标

    Raises:
        ValueError: 当输入无效或变换失败时
    """
    # 验证输入范围
    if not (0.0 - epsilon <= hat_x <= 1.0 + epsilon):
        raise ValueError(f"hat_x 必须在 [0, 1] 范围内，当前值: {hat_x}")
    if not (0.0 - epsilon <= hat_y <= 1.0 + epsilon):
        raise ValueError(f"hat_y 必须在 [0, 1] 范围内，当前值: {hat_y}")

    # 裁剪到有效范围（处理边界附近的浮点误差）
    hat_x = np.clip(hat_x, 0.0, 1.0)
    hat_y = np.clip(hat_y, 0.0, 1.0)

    # 验证多边形是凸的
    if not is_convex_polygon(polygon, epsilon):
        raise ValueError("输入多边形必须是凸多边形")

    # ========== 步骤1: 计算x坐标（使用全局边界）==========
    lb_x, ub_x = get_polygon_x_bounds(polygon)

    if abs(ub_x - lb_x) < epsilon:
        raise ValueError("多边形在x方向上的宽度为零")

    # x = hat_x * (ub_x - lb_x) + lb_x
    x = hat_x * (ub_x - lb_x) + lb_x

    # ========== 步骤2: 计算y坐标（使用局部边界）==========
    # 获取在x处的y局部边界
    lb_y, ub_y = get_vertical_intersection_y_bounds(polygon, x, epsilon)

    if abs(ub_y - lb_y) < epsilon:
        # 如果局部y范围为零，说明x在多边形边界上
        # 此时y取该点的y值
        y = (lb_y + ub_y) / 2
    else:
        # y = hat_y * (ub_y(x) - lb_y(x)) + lb_y(x)
        y = hat_y * (ub_y - lb_y) + lb_y

    return x, y


def verify_point_in_polygon(
    polygon: Polygon,
    x: float,
    y: float,
    epsilon: float = 1e-9
) -> bool:
    """
    验证点是否在多边形内部（包含边界）。

    Args:
        polygon: 多边形对象
        x: x坐标
        y: y坐标
        epsilon: 容差

    Returns:
        True如果在多边形内，False otherwise
    """
    point = Point(x, y)
    return polygon.contains(point) or polygon.boundary.distance(point) < epsilon


def test_coordinate_transformation():
    """
    测试坐标变换算法。

    测试内容：
    1. 网格点映射验证
    2. 边界点验证（hat_x, hat_y 为 0 或 1）
    3. 随机点验证
    4. 可视化（如果matplotlib可用）
    """
    print("=" * 60)
    print("凸多边形坐标变换算法测试")
    print("=" * 60)

    # 创建测试多边形（凸多边形）
    test_polygons = [
        ("正方形", Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])),
        ("三角形", Polygon([(0, 0), (5, 0), (2.5, 5)])),
        ("平行四边形", Polygon([(0, 0), (4, 1), (6, 4), (2, 3)])),
        ("不规则凸多边形", Polygon([(0, 0), (3, 0), (5, 2), (4, 4), (1, 3)])),
    ]

    all_passed = True
    epsilon = 1e-9

    for name, polygon in test_polygons:
        print(f"\n测试多边形: {name}")
        print(f"  边界框: {polygon.bounds}")
        print(f"  面积: {polygon.area:.4f}")

        # 测试1: 网格点
        grid_sizes = [5, 10]
        for n in grid_sizes:
            grid_passed = True
            for i in range(n + 1):
                for j in range(n + 1):
                    hat_x = i / n
                    hat_y = j / n
                    try:
                        x, y = transform_coordinates(polygon, hat_x, hat_y)
                        if not verify_point_in_polygon(polygon, x, y, epsilon):
                            print(f"    网格点失败: ({hat_x}, {hat_y}) -> ({x}, {y})")
                            grid_passed = False
                            all_passed = False
                    except Exception as e:
                        print(f"    网格点异常: ({hat_x}, {hat_y}): {e}")
                        grid_passed = False
                        all_passed = False
            if grid_passed:
                print(f"  网格测试 ({n}x{n}): [PASS]")
            else:
                print(f"  网格测试 ({n}x{n}): [FAIL]")

        # 测试2: 边界点
        boundary_cases = [
            (0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0),
            (0.5, 0.0), (0.5, 1.0), (0.0, 0.5), (1.0, 0.5),
        ]
        boundary_passed = True
        for hat_x, hat_y in boundary_cases:
            try:
                x, y = transform_coordinates(polygon, hat_x, hat_y)
                if not verify_point_in_polygon(polygon, x, y, epsilon):
                    print(f"    边界点失败: ({hat_x}, {hat_y}) -> ({x}, {y})")
                    boundary_passed = False
                    all_passed = False
            except Exception as e:
                print(f"    边界点异常: ({hat_x}, {hat_y}): {e}")
                boundary_passed = False
                all_passed = False
        if boundary_passed:
            print("  边界测试: [PASS]")
        else:
            print("  边界测试: [FAIL]")

        # 测试3: 随机点
        np.random.seed(42)
        n_random = 100
        random_passed = True
        for _ in range(n_random):
            hat_x = np.random.random()
            hat_y = np.random.random()
            try:
                x, y = transform_coordinates(polygon, hat_x, hat_y)
                if not verify_point_in_polygon(polygon, x, y, epsilon):
                    print(f"    随机点失败: ({hat_x}, {hat_y}) -> ({x}, {y})")
                    random_passed = False
                    all_passed = False
            except Exception as e:
                print(f"    随机点异常: ({hat_x}, {hat_y}): {e}")
                random_passed = False
                all_passed = False
        if random_passed:
            print(f"  随机测试 ({n_random}点): [PASS]")
        else:
            print(f"  随机测试 ({n_random}点): [FAIL]")

    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试: [PASS]")
    else:
        print("部分测试: [FAIL]")
    print("=" * 60)

    # 可视化（如果matplotlib可用）
    try:
        visualize_transformation(test_polygons[0][1])
    except ImportError:
        print("\nmatplotlib不可用，跳过可视化")


def visualize_transformation(polygon: Polygon, grid_size: int = 10):
    """
    可视化坐标变换结果。

    Args:
        polygon: 凸多边形
        grid_size: 网格密度
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 左图：归一化空间 [0,1]×[0,1]
    ax1 = axes[0]
    ax1.set_xlim(-0.1, 1.1)
    ax1.set_ylim(-0.1, 1.1)
    ax1.set_aspect('equal')
    ax1.set_title('归一化空间 [0,1]×[0,1]', fontsize=12)
    ax1.set_xlabel('hat_x')
    ax1.set_ylabel('hat_y')
    ax1.grid(True, alpha=0.3)

    # 绘制归一化空间中的网格点
    for i in range(grid_size + 1):
        for j in range(grid_size + 1):
            hat_x = i / grid_size
            hat_y = j / grid_size
            color = plt.cm.viridis((i + j) / (2 * grid_size))
            ax1.plot(hat_x, hat_y, 'o', color=color, markersize=6)

    # 绘制单位正方形边界
    unit_square = plt.Rectangle((0, 0), 1, 1, fill=False, edgecolor='black', linewidth=2)
    ax1.add_patch(unit_square)

    # 右图：物理空间（多边形内）
    ax2 = axes[1]
    ax2.set_aspect('equal')
    ax2.set_title('物理空间（凸多边形内）', fontsize=12)
    ax2.set_xlabel('x')
    ax2.set_ylabel('y')
    ax2.grid(True, alpha=0.3)

    # 绘制多边形
    poly_patch = MplPolygon(list(polygon.exterior.coords)[:-1],
                            fill=True, facecolor='lightblue',
                            edgecolor='black', linewidth=2, alpha=0.5)
    ax2.add_patch(poly_patch)

    # 绘制变换后的点
    for i in range(grid_size + 1):
        for j in range(grid_size + 1):
            hat_x = i / grid_size
            hat_y = j / grid_size
            x, y = transform_coordinates(polygon, hat_x, hat_y)
            color = plt.cm.viridis((i + j) / (2 * grid_size))
            ax2.plot(x, y, 'o', color=color, markersize=6)

    # 设置边界
    minx, miny, maxx, maxy = polygon.bounds
    margin = 0.5
    ax2.set_xlim(minx - margin, maxx + margin)
    ax2.set_ylim(miny - margin, maxy + margin)

    plt.tight_layout()
    plt.savefig('coordinate_transformation.png', dpi=150, bbox_inches='tight')
    print("\n可视化结果已保存到: coordinate_transformation.png")
    plt.show()


if __name__ == "__main__":
    test_coordinate_transformation()
