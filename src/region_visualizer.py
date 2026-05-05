"""
部署区域分解算法的可视化模块

提供多种可视化功能：
1. 完整分解流程可视化
2. 各步骤结果可视化
3. 二进制编码可视化
4. 交互式可视化

作者：Claude Code
日期：2026-03-31
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
from typing import List, Tuple, Dict, Union, Optional
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union

# 颜色配置
COLORS = {
    'original': '#2E86AB',      # 原始多边形
    'components': '#A23B72',    # 连通分量
    'hole_free': '#F18F01',     # 无空洞多边形
    'convex': '#C73E1D',        # 凸多边形
    'codes': ['#1B998B', '#FF9B71', '#E84855', '#3185FC', '#F9C80E']  # 编码颜色
}


class RegionVisualizer:
    """
    区域分解可视化器
    """

    def __init__(self, figsize: Tuple[int, int] = (12, 8)):
        """
        初始化可视化器

        参数:
            figsize: 图形尺寸
        """
        self.figsize = figsize

        # 检查matplotlib是否可用
        try:
            import matplotlib.pyplot as plt
            self.plt = plt
            self.mpatches = mpatches
            self.MATPLOTLIB_AVAILABLE = True
        except ImportError:
            self.MATPLOTLIB_AVAILABLE = False
            print("警告: matplotlib未安装，可视化功能不可用")

    def plot_decomposition_process(
        self,
        original: Union[Polygon, MultiPolygon],
        connected_components: List[Polygon],
        hole_free_polygons: List[Polygon],
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str],
        save_path: Optional[str] = None,
        show_labels: bool = True
    ):
        """
        绘制完整的分解流程

        参数:
            original: 原始多边形
            connected_components: 连通分量
            hole_free_polygons: 无空洞多边形
            convex_polygons: 凸多边形
            binary_codes: 二进制编码
            save_path: 保存路径（可选）
            show_labels: 是否显示标签
        """
        if not self.MATPLOTLIB_AVAILABLE:
            print("无法绘制：matplotlib未安装")
            return

        fig, axes = self.plt.subplots(2, 2, figsize=self.figsize)

        # 1. 原始多边形
        ax = axes[0, 0]
        self._plot_polygon_on_axis(ax, original, color=COLORS['original'])
        ax.set_title("原始多边形", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 添加信息
        if isinstance(original, MultiPolygon):
            component_count = len(list(original.geoms))
        else:
            component_count = 1
        info_text = f"组件数: {component_count}\n面积: {original.area:.2f}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                verticalalignment='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # 2. 连通分量
        ax = axes[0, 1]
        if connected_components:
            for i, component in enumerate(connected_components):
                # 为每个分量分配不同颜色
                color_idx = i % len(COLORS['codes'])
                self._plot_polygon_on_axis(ax, component, color=COLORS['codes'][color_idx])

                if show_labels:
                    # 在重心处添加编号
                    centroid = component.centroid
                    ax.text(centroid.x, centroid.y, f"C{i+1}",
                           ha='center', va='center', fontsize=10,
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        ax.set_title(f"连通分量 ({len(connected_components)}个)", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 3. 无空洞多边形
        ax = axes[1, 0]
        if hole_free_polygons:
            for i, polygon in enumerate(hole_free_polygons):
                # 为每个多边形分配不同颜色
                color_idx = i % len(COLORS['codes'])
                self._plot_polygon_on_axis(ax, polygon, color=COLORS['codes'][color_idx])

                if show_labels:
                    # 显示空洞数量
                    if hasattr(polygon, 'interiors'):
                        hole_count = len(polygon.interiors)
                        if hole_count > 0:
                            centroid = polygon.centroid
                            ax.text(centroid.x, centroid.y, f"H{hole_count}",
                                   ha='center', va='center', fontsize=9,
                                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        ax.set_title(f"无空洞多边形 ({len(hole_free_polygons)}个)", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 4. 凸分解和二进制编码
        ax = axes[1, 1]
        if convex_polygons:
            # 创建颜色映射
            unique_codes = list(set(binary_codes.values()))
            code_to_color = {}
            for i, code in enumerate(unique_codes):
                color_idx = i % len(COLORS['codes'])
                code_to_color[code] = COLORS['codes'][color_idx]

            # 绘制凸多边形
            for idx, polygon in enumerate(convex_polygons):
                if idx in binary_codes:
                    code = binary_codes[idx]
                    color = code_to_color.get(code, COLORS['convex'])
                    self._plot_polygon_on_axis(ax, polygon, color=color, alpha=0.7)

                    if show_labels:
                        # 在重心处添加二进制编码
                        centroid = polygon.centroid
                        ax.text(centroid.x, centroid.y, code,
                               ha='center', va='center', fontsize=10,
                               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        ax.set_title(f"凸分解 ({len(convex_polygons)}个凸多边形)", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 添加图例
        handles = [
            mpatches.Patch(color=COLORS['original'], label='原始多边形'),
            mpatches.Patch(color=COLORS['components'], label='连通分量'),
            mpatches.Patch(color=COLORS['hole_free'], label='无空洞多边形'),
            mpatches.Patch(color=COLORS['convex'], label='凸多边形'),
        ]
        fig.legend(handles=handles, loc='upper center', ncol=4, fontsize=11)

        self.plt.tight_layout(rect=(0, 0.03, 1, 0.95))

        # 添加总标题
        fig.suptitle("部署区域分解算法流程", fontsize=16, fontweight='bold', y=0.98)

        if save_path:
            self.plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图形已保存到: {save_path}")

        self.plt.show()

    def plot_convex_decomposition_details(
        self,
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str],
        original_area: Optional[float] = None,
        save_path: Optional[str] = None
    ):
        """
        详细绘制凸分解结果

        参数:
            convex_polygons: 凸多边形列表
            binary_codes: 二进制编码字典
            original_area: 原始多边形面积（用于计算覆盖率）
            save_path: 保存路径（可选）
        """
        if not self.MATPLOTLIB_AVAILABLE:
            print("无法绘制：matplotlib未安装")
            return

        fig, axes = self.plt.subplots(1, 2, figsize=(14, 6))

        # 1. 凸多边形分布
        ax = axes[0]

        # 为每个凸多边形分配颜色
        patches = []
        colors = []
        code_labels = []

        for idx, polygon in enumerate(convex_polygons):
            # 创建matplotlib多边形补丁
            if polygon.exterior:
                coords = list(polygon.exterior.coords)
                if len(coords) >= 3:  # 至少需要3个点
                    patch = mpatches.Polygon(coords, closed=True)
                    patches.append(patch)

                    # 分配颜色
                    if idx in binary_codes:
                        code = binary_codes[idx]
                        # 根据编码生成颜色
                        color_idx = int(code, 2) % len(COLORS['codes'])
                        colors.append(COLORS['codes'][color_idx])
                        code_labels.append(code)
                    else:
                        colors.append(COLORS['convex'])
                        code_labels.append('')

        # 创建补丁集合
        collection = PatchCollection(patches, alpha=0.8)
        collection.set_facecolors(colors)
        collection.set_edgecolors('black')
        collection.set_linewidth(1)

        ax.add_collection(collection)

        # 添加编码标签
        for patch, label in zip(patches, code_labels):
            if label:
                # 计算补丁中心
                vertices = patch.get_xy()
                centroid = vertices.mean(axis=0)
                ax.text(centroid[0], centroid[1], label,
                       ha='center', va='center', fontsize=9,
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        # 设置坐标轴
        ax.autoscale_view()
        ax.set_aspect('equal')
        ax.set_title(f"凸分解结果 ({len(convex_polygons)}个凸多边形)", fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # 添加统计信息
        stats_text = []
        stats_text.append(f"凸多边形数量: {len(convex_polygons)}")

        if original_area:
            total_convex_area = sum(p.area for p in convex_polygons)
            coverage = (total_convex_area / original_area) * 100
            stats_text.append(f"面积覆盖率: {coverage:.1f}%")

        if binary_codes:
            n_bits = len(next(iter(binary_codes.values())))
            stats_text.append(f"二进制位数: {n_bits}")

        stats_str = "\n".join(stats_text)
        ax.text(0.02, 0.98, stats_str, transform=ax.transAxes,
                verticalalignment='top', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

        # 2. 凸多边形面积分布
        ax = axes[1]

        if convex_polygons:
            areas = [p.area for p in convex_polygons]
            codes = [binary_codes.get(i, f"P{i}") for i in range(len(convex_polygons))]

            # 按面积排序
            sorted_indices = np.argsort(areas)[::-1]  # 从大到小

            sorted_areas = [areas[i] for i in sorted_indices]
            sorted_codes = [codes[i] for i in sorted_indices]

            # 创建条形图
            bars = ax.bar(range(len(sorted_areas)), sorted_areas,
                         color=[COLORS['codes'][i % len(COLORS['codes'])] for i in range(len(sorted_areas))])

            # 添加标签
            ax.set_xticks(range(len(sorted_codes)))
            ax.set_xticklabels(sorted_codes, rotation=45, ha='right')

            # 在条上添加面积值
            for bar, area in zip(bars, sorted_areas):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{area:.3f}', ha='center', va='bottom', fontsize=9)

            ax.set_xlabel('凸多边形编码', fontsize=12)
            ax.set_ylabel('面积', fontsize=12)
            ax.set_title('凸多边形面积分布', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')

            # 添加总统计
            total_area = sum(areas)
            avg_area = total_area / len(areas) if areas else 0
            max_area = max(areas) if areas else 0
            min_area = min(areas) if areas else 0

            stats_text = [
                f"总面积: {total_area:.3f}",
                f"平均面积: {avg_area:.3f}",
                f"最大面积: {max_area:.3f}",
                f"最小面积: {min_area:.3f}"
            ]

            ax.text(0.02, 0.98, "\n".join(stats_text), transform=ax.transAxes,
                    verticalalignment='top', fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

        self.plt.tight_layout()

        if save_path:
            self.plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图形已保存到: {save_path}")

        self.plt.show()

    def plot_step_by_step(
        self,
        step_results: Dict[str, any],
        save_path: Optional[str] = None
    ):
        """
        逐步绘制分解过程

        参数:
            step_results: 包含各步骤结果的字典
            save_path: 保存路径（可选）
        """
        if not self.MATPLOTLIB_AVAILABLE:
            print("无法绘制：matplotlib未安装")
            return

        # 确定步骤数量
        steps = []
        if 'original' in step_results:
            steps.append(('原始多边形', step_results['original']))
        if 'connected_components' in step_results:
            steps.append(('连通分量', step_results['connected_components']))
        if 'hole_free' in step_results:
            steps.append(('无空洞多边形', step_results['hole_free']))
        if 'convex_parts' in step_results:
            steps.append(('凸分解', step_results['convex_parts']))

        n_steps = len(steps)
        if n_steps == 0:
            print("没有可绘制的步骤")
            return

        fig, axes = self.plt.subplots(1, n_steps, figsize=(5*n_steps, 5))

        if n_steps == 1:
            axes = [axes]

        for i, (step_name, data) in enumerate(steps):
            ax = axes[i]

            if step_name == '原始多边形':
                self._plot_polygon_on_axis(ax, data, color=COLORS['original'])

            elif step_name == '连通分量':
                if isinstance(data, list):
                    for j, component in enumerate(data):
                        color_idx = j % len(COLORS['codes'])
                        self._plot_polygon_on_axis(ax, component, color=COLORS['codes'][color_idx])
                else:
                    self._plot_polygon_on_axis(ax, data, color=COLORS['components'])

            elif step_name == '无空洞多边形':
                if isinstance(data, list):
                    for j, polygon in enumerate(data):
                        color_idx = j % len(COLORS['codes'])
                        self._plot_polygon_on_axis(ax, polygon, color=COLORS['codes'][color_idx])
                else:
                    self._plot_polygon_on_axis(ax, data, color=COLORS['hole_free'])

            elif step_name == '凸分解':
                if isinstance(data, list):
                    for j, polygon in enumerate(data):
                        color_idx = j % len(COLORS['codes'])
                        self._plot_polygon_on_axis(ax, polygon, color=COLORS['codes'][color_idx])
                else:
                    self._plot_polygon_on_axis(ax, data, color=COLORS['convex'])

            ax.set_title(f"{step_name}", fontsize=14, fontweight='bold')
            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)

            # 添加信息
            if isinstance(data, list):
                info_text = f"数量: {len(data)}"
                if data:
                    total_area = sum(d.area for d in data)
                    info_text += f"\n总面积: {total_area:.2f}"
            else:
                info_text = f"面积: {data.area:.2f}"

            ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                    verticalalignment='top', fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        self.plt.tight_layout()

        if save_path:
            self.plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图形已保存到: {save_path}")

        self.plt.show()

    def _plot_polygon_on_axis(self, ax, polygon, color=None, alpha=0.7, linewidth=1):
        """
        在坐标轴上绘制多边形

        参数:
            ax: matplotlib坐标轴
            polygon: 要绘制的多边形
            color: 填充颜色
            alpha: 透明度
            linewidth: 线宽
        """
        if color is None:
            color = COLORS['original']

        if isinstance(polygon, MultiPolygon):
            # 绘制多个多边形
            for geom in polygon.geoms:
                if isinstance(geom, Polygon):
                    self._plot_single_polygon(ax, geom, color, alpha, linewidth)
        elif isinstance(polygon, Polygon):
            # 绘制单个多边形
            self._plot_single_polygon(ax, polygon, color, alpha, linewidth)
        elif isinstance(polygon, list):
            # 绘制多边形列表
            for i, poly in enumerate(polygon):
                if isinstance(poly, Polygon):
                    poly_color = color if color != COLORS['original'] else COLORS['codes'][i % len(COLORS['codes'])]
                    self._plot_single_polygon(ax, poly, poly_color, alpha, linewidth)

    def _plot_single_polygon(self, ax, polygon, color, alpha, linewidth):
        """绘制单个多边形"""
        # 绘制外部边界
        if polygon.exterior:
            x, y = polygon.exterior.xy
            ax.fill(x, y, alpha=alpha, fc=color, ec='black', linewidth=linewidth)

        # 绘制空洞
        if hasattr(polygon, 'interiors'):
            for interior in polygon.interiors:
                xi, yi = interior.xy
                ax.fill(xi, yi, fc='white', ec='black', linewidth=linewidth)


# ============================================================================
# 使用示例
# ============================================================================

def example_visualization():
    """可视化示例"""
    from shapely.geometry import Polygon, MultiPolygon

    # 创建一些示例多边形
    print("创建示例多边形...")

    # 1. 带空洞的复杂多边形
    exterior = [(0, 0), (5, 0), (5, 5), (0, 5)]
    hole1 = [(1, 1), (2, 1), (2, 2), (1, 2)]
    hole2 = [(3, 3), (4, 3), (4, 4), (3, 4)]
    complex_polygon = Polygon(exterior, [hole1, hole2])

    # 2. 凹多边形
    concave_polygon = Polygon([
        (0, 0), (4, 0), (4, 2), (2, 2),
        (2, 4), (0, 4)
    ])

    # 3. 不连通的多边形
    polygon1 = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    polygon2 = Polygon([(3, 3), (5, 3), (5, 5), (3, 5)])
    disconnected = MultiPolygon([polygon1, polygon2])

    # 创建可视化器
    visualizer = RegionVisualizer(figsize=(14, 10))

    print("\n1. 绘制复杂多边形的分解流程...")
    # 模拟分解结果
    connected_components = [complex_polygon]  # 连通分量
    hole_free_polygons = [complex_polygon]    # 无空洞多边形（简化）
    convex_polygons = [                       # 凸多边形（模拟）
        Polygon([(0, 0), (2.5, 0), (2.5, 2.5), (0, 2.5)]),
        Polygon([(2.5, 0), (5, 0), (5, 2.5), (2.5, 2.5)]),
        Polygon([(0, 2.5), (2.5, 2.5), (2.5, 5), (0, 5)]),
        Polygon([(2.5, 2.5), (5, 2.5), (5, 5), (2.5, 5)])
    ]
    binary_codes = {0: '00', 1: '01', 2: '10', 3: '11'}

    visualizer.plot_decomposition_process(
        original=complex_polygon,
        connected_components=connected_components,
        hole_free_polygons=hole_free_polygons,
        convex_polygons=convex_polygons,
        binary_codes=binary_codes,
        show_labels=True
    )

    print("\n2. 绘制凸分解细节...")
    visualizer.plot_convex_decomposition_details(
        convex_polygons=convex_polygons,
        binary_codes=binary_codes,
        original_area=complex_polygon.area
    )

    print("\n3. 绘制逐步分解过程...")
    step_results = {
        'original': complex_polygon,
        'connected_components': connected_components,
        'hole_free': hole_free_polygons,
        'convex_parts': convex_polygons
    }

    visualizer.plot_step_by_step(step_results)


# ============================================================================
# 与DeploymentRegionDecomposer的集成
# ============================================================================

class DecompositionVisualizer:
    """
    分解可视化集成类

    与DeploymentRegionDecomposer集成，提供一站式分解和可视化功能

    使用示例:
        >>> from region_decomposition import DeploymentRegionDecomposer
        >>> from visualization import DecompositionVisualizer
        >>> decomposer = DeploymentRegionDecomposer(verbose=False)
        >>> result = decomposer.decompose(polygon)
        >>> viz = DecompositionVisualizer()
        >>> viz.visualize_result(polygon, result, save_path="output.png")
    """

    def __init__(self, figsize: Tuple[int, int] = (14, 10)):
        """
        初始化可视化器

        参数:
            figsize: 图形尺寸
        """
        self.visualizer = RegionVisualizer(figsize=figsize)

    def visualize_result(
        self,
        original: Union[Polygon, MultiPolygon],
        decomposition_result: Tuple[List[Polygon], Dict[int, str], int],
        step_results: Optional[Dict[str, any]] = None,
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        可视化分解结果

        参数:
            original: 原始多边形
            decomposition_result: decompose()方法返回的结果
                (convex_polygons, binary_codes, n_bits)
            step_results: 可选的中间步骤结果
            save_path: 保存路径（可选）
            show: 是否显示图形

        返回:
            matplotlib图形对象
        """
        convex_polygons, binary_codes, n_bits = decomposition_result

        # 如果没有提供步骤结果，创建一个简化的版本
        if step_results is None:
            step_results = {
                'original': original,
                'convex_parts': convex_polygons
            }

        # 创建综合可视化
        fig = self._create_comprehensive_plot(
            original, convex_polygons, binary_codes, step_results, save_path
        )

        if show:
            plt.show()

        return fig

    def _create_comprehensive_plot(
        self,
        original: Union[Polygon, MultiPolygon],
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str],
        step_results: Dict[str, any],
        save_path: Optional[str]
    ):
        """创建综合可视化图表"""
        fig, axes = plt.subplots(2, 2, figsize=self.visualizer.figsize)

        # 1. 原始多边形
        ax = axes[0, 0]
        self.visualizer._plot_polygon_on_axis(ax, original, color=COLORS['original'])
        ax.set_title("原始多边形", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 添加信息
        if isinstance(original, MultiPolygon):
            component_count = len(list(original.geoms))
        else:
            component_count = 1
        info_text = f"类型: {original.geom_type}\n组件: {component_count}\n面积: {original.area:.2f}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                verticalalignment='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # 2. 凸分解结果（带编码）
        ax = axes[0, 1]
        self._plot_convex_with_codes(ax, convex_polygons, binary_codes)
        ax.set_title(f"凸分解结果 ({len(convex_polygons)}个)", fontsize=14, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # 3. 面积统计
        ax = axes[1, 0]
        self._plot_area_statistics(ax, convex_polygons, binary_codes, original.area)

        # 4. 编码分布
        ax = axes[1, 1]
        self._plot_code_distribution(ax, convex_polygons, binary_codes)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        fig.suptitle("部署区域分解结果", fontsize=16, fontweight='bold', y=0.98)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图形已保存到: {save_path}")

        return fig

    def _plot_convex_with_codes(
        self,
        ax,
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str]
    ):
        """绘制带编码的凸多边形"""
        for idx, polygon in enumerate(convex_polygons):
            color_idx = idx % len(COLORS['codes'])
            self.visualizer._plot_polygon_on_axis(
                ax, polygon, color=COLORS['codes'][color_idx], alpha=0.7
            )

            # 添加编码标签
            if idx in binary_codes:
                centroid = polygon.centroid
                code = binary_codes[idx]
                ax.text(centroid.x, centroid.y, code,
                       ha='center', va='center', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    def _plot_area_statistics(
        self,
        ax,
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str],
        original_area: float
    ):
        """绘制面积统计"""
        areas = [p.area for p in convex_polygons]
        codes = [binary_codes.get(i, f"P{i}") for i in range(len(convex_polygons))]

        # 按面积排序
        sorted_indices = np.argsort(areas)[::-1]
        sorted_areas = [areas[i] for i in sorted_indices]
        sorted_codes = [codes[i] for i in sorted_indices]

        # 创建条形图
        colors = [COLORS['codes'][i % len(COLORS['codes'])] for i in range(len(areas))]
        bars = ax.bar(range(len(sorted_areas)), sorted_areas, color=colors)

        # 添加标签
        ax.set_xticks(range(len(sorted_codes)))
        ax.set_xticklabels(sorted_codes, rotation=45, ha='right')
        ax.set_xlabel('凸多边形编码', fontsize=12)
        ax.set_ylabel('面积', fontsize=12)
        ax.set_title('凸多边形面积分布', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')

        # 添加统计信息
        total_area = sum(areas)
        coverage = (total_area / original_area * 100) if original_area > 0 else 0
        stats_text = [
            f"凸多边形数: {len(areas)}",
            f"总面积: {total_area:.3f}",
            f"覆盖率: {coverage:.1f}%"
        ]
        ax.text(0.02, 0.98, "\n".join(stats_text), transform=ax.transAxes,
                verticalalignment='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

    def _plot_code_distribution(
        self,
        ax,
        convex_polygons: List[Polygon],
        binary_codes: Dict[int, str]
    ):
        """绘制编码分布统计"""
        n_bits = len(next(iter(binary_codes.values()))) if binary_codes else 0
        n_polys = len(convex_polygons)

        # 创建饼图数据
        labels = [f"编码 {code}" for code in binary_codes.values()]
        sizes = [p.area for p in convex_polygons]

        # 只显示前8个，其余的合并为"其他"
        if len(labels) > 8:
            top_indices = np.argsort(sizes)[-8:][::-1]
            top_labels = [labels[i] for i in top_indices]
            top_sizes = [sizes[i] for i in top_indices]
            other_size = sum(sizes) - sum(top_sizes)
            if other_size > 0:
                top_labels.append("其他")
                top_sizes.append(other_size)
            labels, sizes = top_labels, top_sizes

        # 绘制饼图
        if sizes:
            colors = [COLORS['codes'][i % len(COLORS['codes'])] for i in range(len(labels))]
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct='%1.1f%%',
                colors=colors, startangle=90
            )
            ax.set_title(f'面积分布 (使用{n_bits}位编码)', fontsize=14, fontweight='bold')

    def visualize_comparison(
        self,
        polygons: List[Tuple[str, Union[Polygon, MultiPolygon]]],
        decomposer,
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        比较多边形的分解结果

        参数:
            polygons: 多边形列表，每项为(名称, 多边形)元组
            decomposer: DeploymentRegionDecomposer实例
            save_path: 保存路径（可选）
            show: 是否显示图形
        """
        n = len(polygons)
        if n == 0:
            return

        # 创建子图
        cols = min(3, n)
        rows = (n + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 5*rows))
        if n == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if rows > 1 else list(axes)

        for i, (name, polygon) in enumerate(polygons):
            ax = axes[i]

            try:
                # 执行分解
                convex_polys, codes, n_bits = decomposer.decompose(polygon)

                # 绘制凸多边形
                for j, poly in enumerate(convex_polys):
                    color_idx = j % len(COLORS['codes'])
                    self.visualizer._plot_polygon_on_axis(
                        ax, poly, color=COLORS['codes'][color_idx], alpha=0.7
                    )

                    # 添加编码标签
                    centroid = poly.centroid
                    code = codes.get(j, str(j))
                    ax.text(centroid.x, centroid.y, code,
                           ha='center', va='center', fontsize=8,
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

                ax.set_title(f"{name}\n({len(convex_polys)}个凸多边形, {n_bits}位)",
                           fontsize=10, fontweight='bold')

            except Exception as e:
                ax.text(0.5, 0.5, f"分解失败\n{str(e)}",
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title(name, fontsize=10)

            ax.set_aspect('equal')
            ax.grid(True, alpha=0.3)

        # 隐藏多余的子图
        for i in range(n, len(axes)):
            axes[i].axis('off')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"对比图已保存到: {save_path}")

        if show:
            plt.show()

        return fig


# ============================================================================
# 使用示例
# ============================================================================

def example_integration():
    """可视化集成示例"""
    print("=" * 60)
    print("可视化集成示例")
    print("=" * 60)

    from region_decomposition import DeploymentRegionDecomposer

    # 创建测试多边形
    test_polygons = [
        ("简单凸多边形", Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])),
        ("凹多边形", Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)])),
        ("带空洞", Polygon([(0, 0), (4, 0), (4, 4), (0, 4)],
                         [[(1, 1), (2, 1), (2, 2), (1, 2)]])),
    ]

    # 创建分解器和可视化器
    decomposer = DeploymentRegionDecomposer(verbose=False)
    viz = DecompositionVisualizer(figsize=(15, 12))

    print("\n1. 可视化单个多边形分解...")
    polygon = test_polygons[2][1]  # 带空洞的多边形
    result = decomposer.decompose(polygon)
    viz.visualize_result(polygon, result, show=False)
    plt.close()
    print("   [完成]")

    print("\n2. 比较多边形分解结果...")
    viz.visualize_comparison(test_polygons, decomposer, show=False)
    plt.close()
    print("   [完成]")

    print("\n" + "=" * 60)
    print("可视化集成示例完成!")
    print("=" * 60)


if __name__ == "__main__":
    example_visualization()
    # example_integration()  # 取消注释以运行集成示例