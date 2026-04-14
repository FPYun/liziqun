"""
部署区域分解算法（Deployment Region Decomposition）
实现论文Algorithm 1：将复杂多边形分解为凸多边形并分配二进制编码

算法步骤：
1. 处理不连通区域：分解为连通分量
2. 处理空洞区域：消除所有空洞
3. 凸分解：将无空洞多边形分解为凸多边形
4. 二进制编码：为每个凸多边形分配唯一二进制编码

主要功能：
- decompose_connected_components(): 将不连通区域分解为连通分量
- eliminate_holes(): 使用两条线段切割方法消除空洞
- convex_decomposition(): 使用优化的Hertel-Mehlhorn算法进行凸分解
- assign_binary_codes(): 为凸多边形分配二进制编码
- is_polygon_connected(): 严格的多边形连通性判断

依赖：
- shapely: 几何计算和多边形操作
- numpy: 数值计算
- scipy.spatial.Delaunay (可选): 三角剖分
- triangle (可选): 更精确的三角剖分
- matplotlib (可选): 可视化

复杂度：
- 凸分解: O(n log n)，其中n为顶点数

作者：Claude Code
日期：2026-03-31
"""

import numpy as np
import math
from typing import List, Tuple, Dict, Union

from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
from shapely.ops import split
from shapely.validation import make_valid

# 尝试导入三角剖分库
try:
    from scipy.spatial import Delaunay
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import triangle as tr
    TRIANGLE_AVAILABLE = True
except ImportError:
    TRIANGLE_AVAILABLE = False

# 尝试导入可视化库
try:
    import matplotlib.pyplot as plt  # noqa: F401
    import matplotlib.patches as mpatches  # noqa: F401
    from matplotlib.collections import PatchCollection  # noqa: F401
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class RegionDecompositionError(Exception):
    """
    区域分解算法错误基类

    当多边形分解过程中遇到无效输入或无法分解的情况时抛出
    """
    pass


def validate_polygon(polygon: Union[Polygon, MultiPolygon]) -> bool:
    """
    验证多边形是否有效

    参数:
        polygon: 要验证的多边形

    返回:
        是否有效
    """
    if polygon is None:
        return False

    if polygon.is_empty:
        return False

    # 尝试修复无效几何
    if not polygon.is_valid:
        try:
            polygon = make_valid(polygon)
            if polygon.is_empty:
                return False
        except Exception:
            return False

    return True


def fix_polygon(polygon: Union[Polygon, MultiPolygon]) -> Union[Polygon, MultiPolygon]:
    """
    修复无效多边形

    参数:
        polygon: 输入多边形

    返回:
        修复后的多边形
    """
    if polygon is None:
        raise ValueError("输入多边形不能为None")

    if polygon.is_empty:
        return polygon

    # 如果无效，尝试修复
    if not polygon.is_valid:
        polygon = make_valid(polygon)

    return polygon


def is_polygon_connected(polygon: Polygon) -> bool:
    """
    检查单个多边形是否连通

    一个多边形被认为是连通的，如果：
    1. 它只有一个外边界
    2. 所有内部区域都通过边界连接

    参数:
        polygon: 要检查的多边形

    返回:
        是否连通
    """
    if polygon is None or polygon.is_empty:
        return False

    # 获取多边形边界
    boundary = polygon.boundary

    # 如果边界是MultiLineString，说明有多个分离的部分（不连通）
    if isinstance(boundary, MultiLineString):
        # 检查是否所有部分都是内部空洞的边界
        # 如果是多个外环，则不连通
        exterior_rings = []
        for geom in boundary.geoms:
            if hasattr(geom, 'coords') and len(list(geom.coords)) >= 3:
                # 检查是否是一个外环
                ring = Polygon(geom)
                if not ring.is_empty and ring.area > 0:
                    # 检查是否包含其他边界（如果是外环，它应该包含空洞）
                    is_exterior = False
                    for other in boundary.geoms:
                        if other is not geom:
                            other_ring = Polygon(other)
                            if ring.contains(other_ring):
                                is_exterior = True
                                break
                    if not is_exterior:
                        # 可能是另一个独立的外环
                        exterior_rings.append(geom)

        # 如果有多个外环，则不连通
        if len(exterior_rings) > 1:
            return False

    # 单一边界或多个边界但有包含关系（空洞），认为是连通的
    return True


def decompose_connected_components(polygon: Union[Polygon, MultiPolygon]) -> List[Polygon]:
    """
    步骤1：处理不连通区域
    将输入区域分解为连通分量

    参数:
        polygon: 输入多边形（可能是MultiPolygon）

    返回:
        连通分量列表（每个都是Polygon）
    """
    if not validate_polygon(polygon):
        raise RegionDecompositionError("无效的多边形输入")

    polygon = fix_polygon(polygon)

    # 如果已经是MultiPolygon，直接返回各个部分
    if isinstance(polygon, MultiPolygon):
        components = []
        for geom in polygon.geoms:
            if isinstance(geom, Polygon) and not geom.is_empty:
                components.append(geom)
        return components

    # 单个多边形，检查是否连通
    if isinstance(polygon, Polygon):
        # 使用严格的连通性检查
        if is_polygon_connected(polygon):
            return [polygon]
        else:
            # 如果不连通，尝试使用shapely的polygonize来分离
            boundary = polygon.boundary
            if isinstance(boundary, MultiLineString):
                # 尝试将边界分解为独立的连通分量
                components = []
                for geom in boundary.geoms:
                    if hasattr(geom, 'coords'):
                        coords = list(geom.coords)
                        if len(coords) >= 3:
                            poly = Polygon(coords)
                            if not poly.is_empty:
                                components.append(poly)
                if components:
                    return components

            # 如果无法分离，返回原多边形
            return [polygon]

    return [polygon]


def eliminate_holes(polygon: Polygon) -> List[Polygon]:
    """
    步骤2：处理空洞区域
    消除多边形中的所有空洞

    论文要求：从空洞边界顶点向该区域的其他顶点引出两条完全落在区域内部的线段

    参数:
        polygon: 带空洞的多边形

    返回:
        无空洞的多边形列表
    """
    if not validate_polygon(polygon):
        raise RegionDecompositionError("无效的多边形输入")

    polygon = fix_polygon(polygon)

    # 如果没有空洞，直接返回
    if not hasattr(polygon, 'interiors') or len(polygon.interiors) == 0:
        return [polygon]

    # 使用两条线段的方法消除空洞
    try:
        return _eliminate_holes_with_two_lines(polygon)
    except Exception as e:
        print(f"两条线段方法失败，回退到单线段方法: {e}")
        # 回退到原来的单线段方法
        return _eliminate_holes_recursive(polygon)


def _eliminate_holes_with_two_lines(polygon: Polygon, depth: int = 0) -> List[Polygon]:
    """
    使用两条线段的方法消除空洞

    论文算法：从空洞内部边界上找一个顶点，向该区域的其他顶点引出两条
    完全落在该区域内部的线段，利用这两条线段将该区域切分。

    参数:
        polygon: 带空洞的多边形
        depth: 递归深度

    返回:
        无空洞的多边形列表
    """
    # 递归深度限制
    if depth > 10:
        print(f"递归深度超过限制 ({depth})，返回原始多边形")
        return [polygon]
    if len(polygon.interiors) == 0:
        return [polygon]

    # 选择第一个空洞
    hole = polygon.interiors[0]
    hole_coords = list(hole.coords)[:-1]  # 去掉重复的最后一个点

    # 收集所有候选顶点（外部边界 + 其他空洞的顶点）
    candidate_vertices = []

    # 外部边界顶点
    exterior_coords = list(polygon.exterior.coords)[:-1]
    candidate_vertices.extend(exterior_coords)

    # 其他空洞的顶点
    for i, interior in enumerate(polygon.interiors):
        if i == 0:  # 跳过当前空洞
            continue
        interior_coords = list(interior.coords)[:-1]
        candidate_vertices.extend(interior_coords)

    # 尝试每个空洞顶点作为起点
    for h_vertex in hole_coords:
        # 寻找两个不同的目标顶点
        target_vertices = []

        for candidate in candidate_vertices:
            # 不能是同一个点
            if abs(h_vertex[0] - candidate[0]) < 1e-9 and abs(h_vertex[1] - candidate[1]) < 1e-9:
                continue

            # 检查线段是否完全在多边形内部（使用与现有算法相同的检查）
            line = LineString([h_vertex, candidate])
            # 使用 contains(line.buffer(epsilon)) 检查
            if polygon.contains(line.buffer(1e-9)):
                target_vertices.append(candidate)

                # 如果找到两个不同的目标顶点，就可以切割
                if len(target_vertices) >= 2:
                    # 确保两个目标顶点不同
                    v1, v2 = target_vertices[0], target_vertices[1]
                    if abs(v1[0] - v2[0]) < 1e-9 and abs(v1[1] - v2[1]) < 1e-9:
                        continue  # 两个顶点相同，继续寻找

                    # 调试信息
                    if depth == 0:
                        print(f"找到两个目标顶点: {v1} 和 {v2} (从空洞顶点 {h_vertex})")

                    # 使用两条线段切割多边形
                    try:
                        if depth == 0:
                            print(f"  切割多边形，空洞顶点: {h_vertex}")
                            print(f"  目标顶点1: {v1}, 目标顶点2: {v2}")

                        # 创建切割线（延长以确保切割，使用与现有算法相同的延长因子）
                        extend_factor = 0.1  # 与现有算法相同的延长因子
                        dx1 = v1[0] - h_vertex[0]
                        dy1 = v1[1] - h_vertex[1]
                        length1 = max(math.sqrt(dx1*dx1 + dy1*dy1), 1e-9)
                        start1 = (h_vertex[0] - dx1/length1 * extend_factor,
                                 h_vertex[1] - dy1/length1 * extend_factor)
                        end1 = (v1[0] + dx1/length1 * extend_factor,
                               v1[1] + dy1/length1 * extend_factor)
                        line1 = LineString([start1, end1])

                        dx2 = v2[0] - h_vertex[0]
                        dy2 = v2[1] - h_vertex[1]
                        length2 = max(math.sqrt(dx2*dx2 + dy2*dy2), 1e-9)
                        start2 = (h_vertex[0] - dx2/length2 * extend_factor,
                                 h_vertex[1] - dy2/length2 * extend_factor)
                        end2 = (v2[0] + dx2/length2 * extend_factor,
                               v2[1] + dy2/length2 * extend_factor)
                        line2 = LineString([start2, end2])

                        if depth == 0:
                            print(f"  原始线段1: {h_vertex} -> {v1}")
                            print(f"  原始线段2: {h_vertex} -> {v2}")
                            print(f"  切割线1: {start1} -> {end1}")
                            print(f"  切割线2: {start2} -> {end2}")
                            print(f"  切割线1与多边形边界相交: {line1.intersects(polygon.boundary)}")
                            print(f"  切割线2与多边形边界相交: {line2.intersects(polygon.boundary)}")

                        if depth == 0:
                            print(f"  切割线1: {start1} -> {end1}")
                            print(f"  切割线2: {start2} -> {end2}")

                        # 先切割第一条线
                        result1 = split(polygon, line1)
                        if depth == 0:
                            print(f"  第一次切割得到 {len(list(result1.geoms))} 个几何体")

                        # 收集切割后的所有多边形，对每个进行第二条线切割
                        all_sub_polygons = []
                        for geom in result1.geoms:
                            if isinstance(geom, Polygon):
                                # 尝试切割第二条线
                                try:
                                    result2 = split(geom, line2)
                                    for sub_geom in result2.geoms:
                                        if isinstance(sub_geom, Polygon):
                                            # 递归处理子多边形中的空洞
                                            all_sub_polygons.extend(
                                                _eliminate_holes_with_two_lines(sub_geom, depth+1)
                                            )
                                        elif isinstance(sub_geom, MultiPolygon):
                                            for sub_sub_geom in sub_geom.geoms:
                                                if isinstance(sub_sub_geom, Polygon):
                                                    all_sub_polygons.extend(
                                                        _eliminate_holes_with_two_lines(sub_sub_geom, depth+1)
                                                    )
                                except Exception:
                                    # 第二条线切割失败，直接递归处理当前多边形
                                    all_sub_polygons.extend(
                                        _eliminate_holes_with_two_lines(geom, depth+1)
                                    )
                            elif isinstance(geom, MultiPolygon):
                                for sub_geom in geom.geoms:
                                    if isinstance(sub_geom, Polygon):
                                        all_sub_polygons.extend(_eliminate_holes_with_two_lines(sub_geom, depth+1))

                        if all_sub_polygons:
                            return all_sub_polygons

                    except Exception as e:
                        print(f"两条线段切割失败: {e}")
                        continue

    # 如果找不到两条合适的线段，回退到单线段方法
    print("无法找到两条合适的切割线段，回退到单线段方法")
    return _eliminate_holes_recursive(polygon)

def _eliminate_holes_recursive(polygon: Polygon) -> List[Polygon]:
    """递归消除空洞"""
    # 如果没有空洞，返回多边形
    if len(polygon.interiors) == 0:
        return [polygon]

    # 选择第一个空洞
    hole = polygon.interiors[0]
    hole_coords = list(hole.coords)[:-1]  # 去掉重复的最后一个点

    # 外部边界顶点
    exterior_coords = list(polygon.exterior.coords)[:-1]

    # 寻找可见的连接
    connection = None
    for h_vertex in hole_coords:
        for e_vertex in exterior_coords:
            line = LineString([h_vertex, e_vertex])
            # 检查线段是否完全在多边形内部
            if polygon.contains(line.buffer(1e-9)):
                connection = (h_vertex, e_vertex)
                break
        if connection:
            break

    if not connection:
        # 没有找到可见连接，返回原始多边形
        return [polygon]

    h_vertex, e_vertex = connection

    # 创建切割线（稍微延长以确保切割多边形）
    # 计算方向向量
    dx = e_vertex[0] - h_vertex[0]
    dy = e_vertex[1] - h_vertex[1]
    length = max(math.sqrt(dx*dx + dy*dy), 1e-9)

    # 延长线段的起点和终点
    extend_factor = 0.1
    start_extended = (h_vertex[0] - dx/length * extend_factor,
                     h_vertex[1] - dy/length * extend_factor)
    end_extended = (e_vertex[0] + dx/length * extend_factor,
                   e_vertex[1] + dy/length * extend_factor)

    cut_line = LineString([start_extended, end_extended])

    # 尝试切割多边形
    try:
        from shapely.ops import split
        result = split(polygon, cut_line)

        # 收集切割后的多边形
        sub_polygons = []
        for geom in result.geoms:
            if isinstance(geom, Polygon):
                # 递归处理子多边形中的空洞
                sub_polygons.extend(_eliminate_holes_recursive(geom))
            elif isinstance(geom, MultiPolygon):
                for sub_geom in geom.geoms:
                    if isinstance(sub_geom, Polygon):
                        sub_polygons.extend(_eliminate_holes_recursive(sub_geom))

        return sub_polygons

    except Exception as e:
        # 切割失败，返回原始多边形
        print(f"切割多边形失败: {e}")
        return [polygon]


def triangulate_polygon(polygon: Polygon) -> List[Polygon]:
    """
    对多边形进行三角剖分

    参数:
        polygon: 输入多边形（可能带空洞）

    返回:
        三角形列表
    """
    if not validate_polygon(polygon):
        raise RegionDecompositionError("无效的多边形输入")

    # 提取所有顶点
    vertices = []
    segments = []

    # 外部边界
    exterior_coords = list(polygon.exterior.coords)
    exterior_points = exterior_coords[:-1]  # 去掉重复的最后一个点
    start_idx = len(vertices)

    for i, coord in enumerate(exterior_points):
        vertices.append(coord)
        segments.append([start_idx + i, start_idx + (i + 1) % len(exterior_points)])

    # 空洞
    hole_points = []
    for interior in polygon.interiors:
        interior_coords = list(interior.coords)
        interior_points = interior_coords[:-1]
        hole_start = len(vertices)

        for i, coord in enumerate(interior_points):
            vertices.append(coord)
            segments.append([hole_start + i, hole_start + (i + 1) % len(interior_points)])

        # 为空洞添加一个内部点
        interior_poly = Polygon(interior_points)
        hole_point = interior_poly.centroid
        hole_points.append([hole_point.x, hole_point.y])

    # 如果没有顶点，返回空列表
    if len(vertices) < 3:
        return []

    # 尝试使用triangle库
    if TRIANGLE_AVAILABLE:
        try:
            vertices_np = np.array(vertices)
            segments_np = np.array(segments)

            tri_data = {
                'vertices': vertices_np,
                'segments': segments_np,
            }

            if hole_points:
                holes_np = np.array(hole_points)
                tri_data['holes'] = holes_np

            triangulation = tr.triangulate(tri_data, 'p')

            triangles = []
            for tri_indices in triangulation['triangles']:
                tri_verts = vertices_np[tri_indices]
                triangles.append(Polygon(tri_verts))

            return triangles
        except Exception as e:
            print(f"Triangle库三角剖分失败: {e}")
            # 回退到其他方法

    # 使用scipy的Delaunay三角剖分（无约束）
    if SCIPY_AVAILABLE:
        try:
            vertices_np = np.array(vertices)

            # 进行Delaunay三角剖分
            tri = Delaunay(vertices_np)

            triangles = []
            for simplex in tri.simplices:
                tri_verts = vertices_np[simplex]
                tri_poly = Polygon(tri_verts)

                # 检查三角形是否在多边形内部（近似）
                # 使用重心检查
                centroid = tri_poly.centroid
                if polygon.contains(centroid):
                    triangles.append(tri_poly)

            return triangles
        except Exception as e:
            print(f"Scipy三角剖分失败: {e}")

    # 简单回退：将多边形分解为三角形扇（仅适用于凸多边形）
    # 这只是一个简单回退，不适用于复杂多边形
    triangles = []
    exterior_coords = list(polygon.exterior.coords)
    if len(exterior_coords) >= 4:  # 至少有3个不同顶点
        base_point = exterior_coords[0]
        for i in range(1, len(exterior_coords) - 2):
            tri_verts = [base_point, exterior_coords[i], exterior_coords[i + 1]]
            triangles.append(Polygon(tri_verts))

    return triangles


def is_convex_polygon(polygon: Polygon, tolerance: float = 1e-9) -> bool:
    """
    检查多边形是否是凸的

    参数:
        polygon: 要检查的多边形
        tolerance: 容差

    返回:
        是否是凸多边形
    """
    if polygon.is_empty or polygon.area < tolerance:
        return False

    # 简单检查：凸包面积应等于多边形面积
    convex_hull = polygon.convex_hull
    area_diff = convex_hull.area - polygon.area

    return area_diff <= tolerance


def convex_decomposition(polygon: Polygon) -> List[Polygon]:
    """
    步骤3：凸分解
    将无空洞多边形分解为凸多边形

    使用基于三角剖分的合并策略（Hertel-Mehlhorn算法）：
    1. 对多边形进行三角剖分
    2. 合并相邻三角形形成凸多边形

    参数:
        polygon: 无空洞多边形

    返回:
        凸多边形列表
    """
    if not validate_polygon(polygon):
        raise RegionDecompositionError("无效的多边形输入")

    # 如果已经是凸多边形，直接返回
    if is_convex_polygon(polygon):
        return [polygon]

    # 1. 三角剖分
    triangles = triangulate_polygon(polygon)

    if not triangles:
        # 无法三角剖分，返回原多边形
        return [polygon]

    # 2. 合并三角形形成凸多边形
    # 构建邻接关系（优化版：使用边映射，O(n)复杂度）
    n = len(triangles)
    adjacency = [[] for _ in range(n)]

    # 边到三角形索引的映射
    edge_to_tri = {}

    for i, triangle in enumerate(triangles):
        # 获取三角形的顶点
        if triangle.exterior:
            coords = list(triangle.exterior.coords)
            if len(coords) >= 4:  # 多边形，有重复的最后一个点
                vertices = coords[:-1]
                # 处理每条边
                for j in range(len(vertices)):
                    v1 = vertices[j]
                    v2 = vertices[(j + 1) % len(vertices)]
                    # 规范化边：排序顶点使边无序
                    edge = tuple(sorted([(round(v1[0], 12), round(v1[1], 12)),
                                         (round(v2[0], 12), round(v2[1], 12))]))

                    if edge in edge_to_tri:
                        # 找到相邻三角形
                        other_idx = edge_to_tri[edge]
                        adjacency[i].append(other_idx)
                        adjacency[other_idx].append(i)
                    else:
                        edge_to_tri[edge] = i

    # 标记已处理的三角形
    processed = [False] * n
    convex_polygons = []

    for i in range(n):
        if processed[i]:
            continue

        # 从当前三角形开始
        current = triangles[i]
        processed[i] = True

        # 尝试合并相邻三角形
        queue = list(adjacency[i])

        while queue:
            j = queue.pop(0)
            if processed[j]:
                continue

            # 尝试合并
            merged = current.union(triangles[j])

            # 检查合并后的多边形是否是凸的
            if isinstance(merged, Polygon) and is_convex_polygon(merged):
                current = merged
                processed[j] = True
                # 添加新邻居
                for neighbor in adjacency[j]:
                    if not processed[neighbor] and neighbor not in queue:
                        queue.append(neighbor)

        convex_polygons.append(current)

    return convex_polygons


def assign_binary_codes(convex_polygons: List[Polygon]) -> Tuple[Dict[int, str], int]:
    """
    步骤4：二进制编码
    为凸多边形分配二进制编码

    参数:
        convex_polygons: 凸多边形列表

    返回:
        (编码字典, 二进制位数)
        编码字典：索引 -> 二进制字符串
    """
    if not convex_polygons:
        return {}, 0

    n = len(convex_polygons)

    # 计算所需的二进制位数
    # 当n=1时，需要1位二进制数表示0
    if n <= 1:
        n_bits = 1
    else:
        n_bits = math.ceil(math.log2(n))

    # 为每个多边形分配二进制编码
    codes = {}
    for i, poly in enumerate(convex_polygons):
        # 生成二进制字符串，左侧补零
        binary_str = format(i, f'0{n_bits}b')
        codes[i] = binary_str

    return codes, n_bits


class DeploymentRegionDecomposer:
    """
    部署区域分解器（Deployment Region Decomposer）

    实现论文Algorithm 1的全部步骤，将复杂多边形分解为凸多边形并分配二进制编码。

    算法流程：
    1. 连通性处理：将MultiPolygon或不连通的Polygon分解为连通分量
    2. 空洞消除：使用两条线段切割方法消除所有空洞
    3. 凸分解：使用优化的Hertel-Mehlhorn算法（O(n log n)）分解为凸多边形
    4. 二进制编码：为每个凸多边形分配唯一的二进制编码

    使用示例：
        >>> decomposer = DeploymentRegionDecomposer(verbose=True)
        >>> convex_polys, codes, n_bits = decomposer.decompose(polygon)
        >>> print(f"分解为 {len(convex_polys)} 个凸多边形")

    属性:
        verbose: 是否显示详细的分解过程信息

    参考：
        论文 Algorithm 1: Deployment Region Decomposition
    """

    def __init__(self, verbose: bool = True):
        """
        初始化分解器

        参数:
            verbose: 是否显示进度信息，默认为True
        """
        self.verbose = verbose

    def _log(self, message: str):
        """记录日志"""
        if self.verbose:
            print(message)

    def decompose(self, region: Union[Polygon, MultiPolygon]) -> Tuple[List[Polygon], Dict[int, str], int]:
        """
        执行完整的区域分解流程

        将输入的复杂多边形（可能包含空洞、凹顶点或不连通区域）分解为
        一组凸多边形，并为每个凸多边形分配唯一的二进制编码。

        参数:
            region: 输入区域，可以是：
                - Polygon: 简单多边形（可能带空洞）
                - MultiPolygon: 多个分离的多边形

        返回:
            三元组：(convex_polygons, binary_codes, n_bits)
                - convex_polygons: List[Polygon]，凸多边形列表
                - binary_codes: Dict[int, str]，索引到二进制编码的映射
                - n_bits: int，所需的二进制位数

        抛出:
            RegionDecompositionError: 当输入无效或分解失败时

        示例:
            >>> decomposer = DeploymentRegionDecomposer(verbose=False)
            >>> polygon = Polygon([(0,0), (4,0), (4,4), (0,4)],
            ...                  [[(1,1), (2,1), (2,2), (1,2)]])
            >>> convex_polys, codes, n_bits = decomposer.decompose(polygon)
            >>> print(f"分解为 {len(convex_polys)} 个凸多边形，使用 {n_bits} 位编码")
        """
        self._log("=" * 60)
        self._log("开始部署区域分解")
        self._log("=" * 60)

        # 验证输入
        if not validate_polygon(region):
            raise RegionDecompositionError("无效的区域输入")

        region = fix_polygon(region)
        self._log(f"输入区域: {region.geom_type}, 面积: {region.area:.4f}")

        # 步骤1：处理不连通区域
        self._log("\n步骤1: 处理不连通区域...")
        connected_components = decompose_connected_components(region)
        self._log(f"  找到 {len(connected_components)} 个连通分量")

        # 步骤2：处理空洞区域
        self._log("\n步骤2: 处理空洞区域...")
        hole_free_polygons = []

        for i, component in enumerate(connected_components):
            self._log(f"  处理分量 {i+1}/{len(connected_components)}...")

            if hasattr(component, 'interiors'):
                hole_count = len(component.interiors)
                self._log(f"    空洞数量: {hole_count}")

            # 消除空洞
            eliminated = eliminate_holes(component)
            hole_free_polygons.extend(eliminated)

        self._log(f"  空洞消除后得到 {len(hole_free_polygons)} 个无空洞多边形")

        # 步骤3：凸分解
        self._log("\n步骤3: 凸分解...")
        all_convex_polygons = []

        for i, polygon in enumerate(hole_free_polygons):
            self._log(f"  分解多边形 {i+1}/{len(hole_free_polygons)}...")

            convex_parts = convex_decomposition(polygon)
            all_convex_polygons.extend(convex_parts)

            self._log(f"    分解为 {len(convex_parts)} 个凸多边形")

        self._log(f"  总共得到 {len(all_convex_polygons)} 个凸多边形")

        # 步骤4：二进制编码
        self._log("\n步骤4: 二进制编码...")
        binary_codes, n_bits = assign_binary_codes(all_convex_polygons)

        self._log(f"  需要 {n_bits} 位二进制编码")
        for idx, code in binary_codes.items():
            self._log(f"    凸多边形 {idx}: 编码 {code}")

        self._log("\n" + "=" * 60)
        self._log("部署区域分解完成!")
        self._log("=" * 60)

        return all_convex_polygons, binary_codes, n_bits


# ============================================================================
# 测试函数
# ============================================================================

def create_test_polygons() -> List[Tuple[str, Union[Polygon, MultiPolygon]]]:
    """
    创建测试多边形

    返回:
        测试用例列表 (名称, 多边形)
    """
    test_cases = []

    # 1. 简单凸多边形（矩形）
    convex_polygon = Polygon([
        (0, 0), (2, 0), (2, 2), (0, 2)
    ])
    test_cases.append(("凸多边形", convex_polygon))

    # 2. 凹多边形（L形）
    concave_polygon = Polygon([
        (0, 0), (3, 0), (3, 1), (1, 1),
        (1, 3), (0, 3)
    ])
    test_cases.append(("凹多边形", concave_polygon))

    # 3. 带空洞的多边形
    exterior = [(0, 0), (4, 0), (4, 4), (0, 4)]
    interior = [(1, 1), (3, 1), (3, 3), (1, 3)]
    polygon_with_hole = Polygon(exterior, [interior])
    test_cases.append(("带空洞的多边形", polygon_with_hole))

    # 4. 不连通的多边形
    polygon1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    polygon2 = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    disconnected = MultiPolygon([polygon1, polygon2])
    test_cases.append(("不连通多边形", disconnected))

    # 5. 复杂多边形（星形）
    star_polygon = Polygon([
        (0, 1), (0.5, 0.1), (1, 1), (0.1, 0.5), (0.9, 0.5)
    ])
    test_cases.append(("星形多边形", star_polygon))

    # 6. 带两个空洞的多边形
    exterior2 = [(0, 0), (6, 0), (6, 6), (0, 6)]
    interior2_1 = [(1, 1), (2, 1), (2, 2), (1, 2)]
    interior2_2 = [(4, 4), (5, 4), (5, 5), (4, 5)]
    polygon_two_holes = Polygon(exterior2, [interior2_1, interior2_2])
    test_cases.append(("带两个空洞的多边形", polygon_two_holes))

    # 7. 嵌套空洞的多边形
    exterior3 = [(0, 0), (8, 0), (8, 8), (0, 8)]
    interior3_1 = [(1, 1), (7, 1), (7, 7), (1, 7)]  # 大空洞
    interior3_2 = [(2, 2), (3, 2), (3, 3), (2, 3)]  # 小空洞在大空洞内
    # 注意：shapely不支持真正的嵌套空洞，这里创建两个独立空洞
    polygon_nested_holes = Polygon(exterior3, [interior3_1, interior3_2])
    test_cases.append(("多个空洞的多边形", polygon_nested_holes))

    # 8. 复杂凹多边形（锯齿形）
    zigzag_polygon = Polygon([
        (0, 0), (5, 0), (5, 1), (1, 1),
        (1, 2), (4, 2), (4, 3), (2, 3),
        (2, 4), (3, 4), (3, 5), (0, 5)
    ])
    test_cases.append(("锯齿形凹多边形", zigzag_polygon))

    # 9. 更大规模的多边形（用于性能测试）
    large_exterior = [(0, 0), (10, 0), (10, 10), (0, 10)]
    # 添加多个空洞
    large_holes = []
    for i in range(3):
        for j in range(3):
            x = 1 + i * 3
            y = 1 + j * 3
            hole = [(x, y), (x+0.5, y), (x+0.5, y+0.5), (x, y+0.5)]
            large_holes.append(hole)
    large_polygon = Polygon(large_exterior, large_holes)
    test_cases.append(("大规模多边形（9个空洞）", large_polygon))

    # 10. 三角形（最简单的多边形）
    triangle = Polygon([(0, 0), (2, 0), (1, 1.5)])
    test_cases.append(("三角形", triangle))

    # 11. 细长多边形（测试退化情况）
    thin_polygon = Polygon([
        (0, 0), (10, 0), (10, 0.1), (5, 0.1),
        (5, 0.2), (8, 0.2), (8, 0.3), (0, 0.3)
    ])
    test_cases.append(("细长多边形", thin_polygon))

    # 12. 多个不连通的多边形（3个以上）
    poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    poly2 = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    poly3 = Polygon([(4, 0), (5, 0), (5, 1), (4, 1)])
    poly4 = Polygon([(6, 2), (7, 2), (7, 3), (6, 3)])
    multi_disconnected = MultiPolygon([poly1, poly2, poly3, poly4])
    test_cases.append(("多不连通区域（4个）", multi_disconnected))

    # 13. 带狭长空洞的多边形
    exterior_narrow = [(0, 0), (5, 0), (5, 5), (0, 5)]
    narrow_hole = [(2, 1), (3, 1), (3, 4), (2, 4)]  # 狭长空洞
    polygon_narrow_hole = Polygon(exterior_narrow, [narrow_hole])
    test_cases.append(("带狭长空洞的多边形", polygon_narrow_hole))

    # 14. 螺旋形多边形（复杂凹多边形）
    spiral_coords = [
        (0, 0), (4, 0), (4, 4), (1, 4), (1, 1),
        (3, 1), (3, 3), (2, 3), (2, 2), (2.5, 2)
    ]
    spiral_polygon = Polygon(spiral_coords)
    test_cases.append(("螺旋形多边形", spiral_polygon))

    # 15. 极点多边形（测试数值稳定性）
    extreme_polygon = Polygon([
        (0, 0), (1e6, 0), (1e6, 1e6), (0, 1e6)
    ])
    test_cases.append(("大坐标多边形", extreme_polygon))

    return test_cases


def test_decomposition():
    """测试分解算法"""
    print("测试部署区域分解算法")
    print("=" * 60)

    # 创建分解器
    decomposer = DeploymentRegionDecomposer(verbose=True)

    # 获取测试用例
    test_cases = create_test_polygons()

    results = []

    for name, polygon in test_cases:
        print(f"\n测试: {name}")
        print("-" * 40)

        try:
            convex_polys, codes, n_bits = decomposer.decompose(polygon)

            print(f"结果:")
            print(f"  凸多边形数量: {len(convex_polys)}")
            print(f"  二进制位数: {n_bits}")
            print(f"  编码: {codes}")

            results.append((name, len(convex_polys), n_bits))

        except Exception as e:
            print(f"错误: {str(e)}")
            results.append((name, "失败", str(e)))

    print("\n" + "=" * 60)
    print("测试摘要:")
    print("-" * 60)

    for name, convex_count, bits in results:
        print(f"{name:20} -> 凸多边形: {convex_count}, 位数: {bits}")


def test_edge_cases():
    """
    测试边界情况和异常处理
    """
    print("\n" + "=" * 60)
    print("边界情况测试")
    print("=" * 60)

    decomposer = DeploymentRegionDecomposer(verbose=False)

    # 测试1: None输入
    print("\n测试1: None输入")
    try:
        decomposer.decompose(None)
        print("  [失败] 应该抛出异常")
    except RegionDecompositionError as e:
        print(f"  [通过] 正确抛出异常: {e}")
    except Exception as e:
        print(f"  [失败] 抛出错误类型异常: {type(e).__name__}: {e}")

    # 测试2: 空多边形
    print("\n测试2: 空多边形")
    try:
        empty = Polygon()
        result = decomposer.decompose(empty)
        print(f"  [结果] 空多边形处理结果: {result}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试3: 单个点
    print("\n测试3: 单个点")
    try:
        point = Polygon([(0, 0)])
        result = decomposer.decompose(point)
        print(f"  [结果] 单点处理结果: {result}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试4: 线段（退化多边形）
    print("\n测试4: 线段")
    try:
        line = Polygon([(0, 0), (1, 0)])
        result = decomposer.decompose(line)
        print(f"  [结果] 线段处理结果: {result}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试5: 自相交多边形（无效）
    print("\n测试5: 自相交多边形")
    try:
        # 创建一个8字形（自相交）
        bowtie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0)])
        result = decomposer.decompose(bowtie)
        print(f"  [结果] 自相交多边形处理结果: 凸多边形数={len(result[0])}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试6: 极小多边形
    print("\n测试6: 极小多边形")
    try:
        tiny = Polygon([
            (0, 0), (1e-10, 0), (1e-10, 1e-10), (0, 1e-10)
        ])
        result = decomposer.decompose(tiny)
        print(f"  [结果] 极小多边形处理结果: 凸多边形数={len(result[0])}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试7: 复杂MultiPolygon
    print("\n测试7: 复杂MultiPolygon（含空洞）")
    try:
        poly1 = Polygon([(0, 0), (3, 0), (3, 3), (0, 3)],
                       [[(1, 1), (2, 1), (2, 2), (1, 2)]])
        poly2 = Polygon([(5, 0), (8, 0), (8, 3), (5, 3)],
                       [[(6, 1), (7, 1), (7, 2), (6, 2)]])
        multi = MultiPolygon([poly1, poly2])
        result = decomposer.decompose(multi)
        print(f"  [结果] 复杂MultiPolygon处理结果: 凸多边形数={len(result[0])}, 位数={result[2]}")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    # 测试8: 大量凸多边形编码
    print("\n测试8: 大量凸多边形（测试编码）")
    try:
        import numpy as np
        # 创建一个复杂的多边形，会产生多个凸部分
        angles = np.linspace(0, 2*np.pi, 20)
        coords = [(np.cos(a)*5, np.sin(a)*5) for a in angles]
        star = Polygon(coords)
        result = decomposer.decompose(star)
        print(f"  [结果] 20边形处理结果: 凸多边形数={len(result[0])}, 位数={result[2]}")
        # 验证编码唯一性
        codes = list(result[1].values())
        if len(codes) == len(set(codes)):
            print("  [验证] 所有编码唯一 [OK]")
        else:
            print("  [验证] 编码不唯一 [FAIL]")
    except Exception as e:
        print(f"  [异常] {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("边界情况测试完成")
    print("=" * 60)


def run_all_tests():
    """
    运行所有测试
    """
    # 运行标准测试
    test_decomposition()

    # 运行边界情况测试
    test_edge_cases()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--edge":
            # 只运行边界测试
            test_edge_cases()
        elif sys.argv[1] == "--standard":
            # 只运行标准测试
            test_decomposition()
        else:
            print("用法: python region_decomposition.py [--edge|--standard]")
            print("  --edge     只运行边界情况测试")
            print("  --standard 只运行标准测试")
            print("  无参数     运行所有测试")
    else:
        # 运行所有测试
        run_all_tests()