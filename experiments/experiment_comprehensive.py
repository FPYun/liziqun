"""
综合任务脚本：处理4个用户请求
1. 增大区域并且进行测试
2. 可视化pareto前沿分布
3. 深入分析两个目标函数的关系
4. 给两个目标函数分配不同的权重综合后再得到pareto解
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
import sys
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.coordinate_transform import transform_coordinates, is_convex_polygon
from src.evaluation import (
    RadarConfig, TaskPoint, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, evaluate_deployment, evaluate_deployment_normalized,
    create_normalized_evaluate_function
)
from src.mopso import MOPSO_DT
from src.benchmarks import find_knee_point, get_extreme_points
from src.pareto_visualization import plot_pareto_front_enhanced

from shapely.geometry import Polygon as ShapelyPolygon


def run_large_region_test():
    """任务1: 增大区域并且进行测试"""
    print("\n" + "="*70)
    print("任务1: 增大区域测试 (200km x 200km, 10 radars)")
    print("="*70)

    # 创建更大区域
    region_coords = [(0, 0), (200, 0), (200, 200), (0, 200)]
    region = ShapelyPolygon(region_coords)

    # 区域分解
    print("\n[1] 区域分解...")
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    print(f"    分解得到 {len(polygons)} 个凸多边形")

    # 雷达配置 - 使用更小的beta增加覆盖难度
    radar_configs = [
        RadarConfig(P0=0.95, P_min=0.8, beta=0.01, is_air=True)
        for _ in range(10)
    ]

    # 生成任务点
    print("\n[2] 生成任务点...")
    task_points = generate_uniform_task_points(region, grid_size=20)
    print(f"    生成 {len(task_points)} 个任务点")

    # MOPSO优化
    print("\n[3] MOPSO优化...")
    J = 10  # 雷达数量
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    print(f"    J={J}, N_bin={N_bin}, 最大迭代=50")

    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.001
    )

    mopso = MOPSO_DT(
        J=J,
        N_bin=N_bin,
        evaluate_func=evaluate_func,
        N_P=50,
        T_max=50,
        verbose=True
    )

    pareto_archive, stats = mopso.optimize()

    print(f"\n[4] 优化结果:")
    print(f"    Pareto解数量: {len(pareto_archive)}")

    if len(pareto_archive) > 0:
        # 从archive中提取解
        pareto_solutions = []
        objectives_list = []

        for entry in pareto_archive:
            sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
            pareto_solutions.append(sol)
            objectives_list.append(entry['objectives'])

        objectives = np.array(objectives_list)
        print(f"    f1范围: [{objectives[:,0].min():.4f}, {objectives[:,0].max():.4f}]")
        print(f"    f2范围: [{objectives[:,1].min():.4f}, {objectives[:,1].max():.4f}]")

        # 计算每个解的ECR和J_min
        ecr_list = []
        j_min_list = []

        for i, sol in enumerate(pareto_solutions):
            continuous = sol[:, :2].flatten()
            binary = sol[:, 2:2+N_bin]
            positions = decode_particle(continuous, binary, J, N_bin, polygons)
            positions_array = np.array(positions)

            ecr = calculate_ecr(
                positions_array, task_points, radar_configs,
                convex_polygons=polygons,
                binary_codes=binary,
                continuous_coords=continuous.reshape(J, 2)
            )
            j_min = calculate_jamming_density(
                positions_array, task_points, radar_configs,
                convex_polygons=polygons,
                binary_codes=binary,
                continuous_coords=continuous.reshape(J, 2)
            )
            ecr_list.append(ecr)
            j_min_list.append(j_min)

        ecr_array = np.array(ecr_list)
        j_min_array = np.array(j_min_list)

        print(f"    ECR范围: [{ecr_array.min():.4f}, {ecr_array.max():.4f}]")
        print(f"    J_min范围: [{j_min_array.min():.6f}, {j_min_array.max():.6f}]")

    if len(pareto_archive) > 0:
        # 从archive中提取解
        pareto_solutions = []
        objectives_list = []

        for entry in pareto_archive:
            sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
            pareto_solutions.append(sol)
            objectives_list.append(entry['objectives'])

        objectives = np.array(objectives_list)
    else:
        pareto_solutions = None
        objectives = None

    return pareto_solutions, objectives, polygons, task_points, radar_configs, J, N_bin, ecr_array if len(pareto_archive) > 0 else None, j_min_array if len(pareto_archive) > 0 else None


def visualize_pareto_front(pareto_solutions, objectives, save_path=None):
    """任务2: 可视化pareto前沿分布（增强版：拐点检测 + 颜色梯度）"""
    print("\n" + "="*70)
    print("任务2: 可视化Pareto前沿分布")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) == 0:
        print("    [警告] 没有Pareto解可可视化")
        return

    print(f"    可视化 {len(pareto_solutions)} 个Pareto解")

    # 拐点检测
    if len(objectives) >= 3:
        knee_idx = find_knee_point(objectives)
        print(f"    拐点 (Knee Point): #{knee_idx}, "
              f"f1={objectives[knee_idx, 0]:.4f}, f2={objectives[knee_idx, 1]:.6f}")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 图1: Pareto前沿 (增强版：颜色梯度 + 拐点标注)
    ax1 = axes[0]
    if len(objectives) >= 3:
        best_cov_idx, best_int_idx, knee_idx = get_extreme_points(objectives)
        colors = plt.cm.RdYlGn(np.linspace(0.3, 1, len(objectives)))
        ax1.scatter(objectives[:, 0], objectives[:, 1], c=colors,
                    s=100, alpha=0.85, edgecolors='black', linewidth=0.5)

        # 标注关键点
        for idx, label, color, offset in [
            (best_cov_idx, 'Best ECR', 'darkred', (10, 20)),
            (best_int_idx, 'Best J_min', 'darkblue', (-50, -25)),
            (knee_idx, 'Knee', 'darkgreen', (20, -20)),
        ]:
            ax1.annotate(f'{label}\n({objectives[idx, 0]:.4f}, {objectives[idx, 1]:.4f})',
                         (objectives[idx, 0], objectives[idx, 1]),
                         xytext=offset, textcoords='offset points', fontsize=9,
                         arrowprops=dict(arrowstyle='->', color=color, lw=1.2),
                         color=color, fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    else:
        ax1.scatter(objectives[:, 0], objectives[:, 1], c='blue',
                    s=100, alpha=0.7, edgecolors='black')

    ax1.set_xlabel('f1 = 1 - ECR', fontsize=12)
    ax1.set_ylabel('f2 = J_norm (归一化干扰功率)', fontsize=12)
    ax1.set_title('Pareto前沿分布', fontsize=14)
    ax1.grid(True, alpha=0.3)

    # 标注最优点
    pareto_obj = objectives[np.argsort(objectives[:, 0])]
    ax1.plot(pareto_obj[:, 0], pareto_obj[:, 1], 'r--', alpha=0.5, label='Pareto边界')
    ax1.legend()

    # 图2: f1和f2的分布直方图
    ax2 = axes[1]
    ax2.hist(objectives[:, 0], bins=10, alpha=0.7, label='f1 (1-ECR)', color='blue')
    ax2hist2 = ax2.twinx()
    ax2hist2.hist(objectives[:, 1], bins=10, alpha=0.5, label='f2 (J_norm)', color='red')
    ax2.set_xlabel('目标函数值', fontsize=12)
    ax2.set_ylabel('f1 频数', color='blue', fontsize=12)
    ax2hist2.set_ylabel('f2 频数', color='red', fontsize=12)
    ax2.set_title('目标函数值分布', fontsize=14)
    ax2.legend(loc='upper left')
    ax2hist2.legend(loc='upper right')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"    图像已保存: {save_path}")

    plt.close()


def analyze_objective_relationship(pareto_solutions, objectives, ecr_values, j_min_values):
    """任务3: 深入分析两个目标函数的关系"""
    print("\n" + "="*70)
    print("任务3: 深入分析两个目标函数的关系")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) < 3:
        print("    [警告] Pareto解数量不足，无法进行深入分析")
        return

    if ecr_values is None or j_min_values is None:
        print("    [警告] 缺少ECR或J_min数据")
        return

    print(f"    分析 {len(pareto_solutions)} 个Pareto解的目标函数关系")

    ecr_values = np.array(ecr_values)
    j_min_values = np.array(j_min_values)

    # 相关性分析
    correlation = np.corrcoef(ecr_values, j_min_values)[0, 1]

    print("\n    === 统计分析 ===")
    print(f"    ECR范围: [{ecr_values.min():.4f}, {ecr_values.max():.4f}]")
    print(f"    J_min范围: [{j_min_values.min():.6f}, {j_min_values.max():.6f}]")
    print(f"    ECR与J_min的相关系数: {correlation:.4f}")

    if correlation < -0.5:
        print("    结论: f1与f2存在强负相关")
        print("    说明覆盖率和干扰压制效能之间存在矛盾")
        print("    需要在两者之间进行权衡")
    elif correlation < 0:
        print("    结论: f1与f2存在中等负相关")
        print("    说明覆盖率增加会略微降低干扰压制能力")
    else:
        print("    结论: f1与f2存在正相关或不相关")
        print("    说明两个目标可能可以同时优化")

    # 分析权衡情况
    print("\n    === 权衡分析 ===")
    sorted_idx = np.argsort(ecr_values)

    print(f"    ECR最低解: ECR={ecr_values[sorted_idx[0]]:.4f}, J_min={j_min_values[sorted_idx[0]]:.6f}")
    print(f"    ECR最高解: ECR={ecr_values[sorted_idx[-1]]:.4f}, J_min={j_min_values[sorted_idx[-1]]:.6f}")

    ecr_range = ecr_values.max() - ecr_values.min()
    j_range = j_min_values.max() - j_min_values.min()

    if ecr_range > 0.1:
        print(f"    ECR变化范围大 ({ecr_range:.4f})，说明算法探索了不同的覆盖水平")
    if j_range > 1e-5:
        print(f"    J_min变化范围: {j_range:.6f}")

    return correlation, ecr_values, j_min_values


def weighted_pareto_analysis(pareto_solutions, objectives, polygons, task_points, radar_configs, J, N_bin):
    """任务4: 给两个目标函数分配不同的权重综合后再得到pareto解"""
    print("\n" + "="*70)
    print("任务4: 权重综合Pareto解分析")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) < 2:
        print("    [警告] Pareto解数量不足")
        return

    # 使用不同的权重组合
    weights = [
        (0.9, 0.1),  # 优先ECR
        (0.7, 0.3),
        (0.5, 0.5),  # 平衡
        (0.3, 0.7),
        (0.1, 0.9),  # 优先J_min
    ]

    print("\n    === 不同权重下的综合目标值 ===")
    print("    权重 (w1, w2) | 综合目标 F = w1*f1 + w2*f2 | 对应ECR | 对应J_min")

    results = []
    for w1, w2 in weights:
        weighted_obj = w1 * objectives[:, 0] + w2 * objectives[:, 1]

        best_idx = np.argmin(weighted_obj)
        best_obj = objectives[best_idx]
        best_sol = pareto_solutions[best_idx]

        # 计算该解的实际ECR和J_min
        continuous = best_sol[:, :2].flatten()
        binary = best_sol[:, 2:2+N_bin]
        positions = decode_particle(continuous, binary, J, N_bin, polygons)
        positions_array = np.array(positions)

        ecr = calculate_ecr(
            positions_array, task_points, radar_configs,
            convex_polygons=polygons,
            binary_codes=binary,
            continuous_coords=continuous.reshape(J, 2)
        )
        j_min = calculate_jamming_density(
            positions_array, task_points, radar_configs,
            convex_polygons=polygons,
            binary_codes=binary,
            continuous_coords=continuous.reshape(J, 2)
        )

        print(f"    ({w1:.1f}, {w2:.1f})        | {weighted_obj[best_idx]:.6f}           | {ecr:.4f}   | {j_min:.6f}")

        results.append({
            'weights': (w1, w2),
            'weighted_obj': weighted_obj[best_idx],
            'ecr': ecr,
            'j_min': j_min,
            'solution': best_sol
        })

    # 可视化权重影响
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 图1: ECR vs 权重
    ax1 = axes[0]
    ecr_vals = [r['ecr'] for r in results]
    ax1.plot([w[0] for w in weights], ecr_vals, 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('w1 (ECR权重)', fontsize=12)
    ax1.set_ylabel('ECR', fontsize=12)
    ax1.set_title('权重 vs ECR', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 1)

    # 图2: J_min vs 权重
    ax2 = axes[1]
    j_vals = [r['j_min'] for r in results]
    ax2.plot([w[0] for w in weights], j_vals, 'r-o', linewidth=2, markersize=8)
    ax2.set_xlabel('w1 (ECR权重)', fontsize=12)
    ax2.set_ylabel('J_min', fontsize=12)
    ax2.set_title('权重 vs 最小干扰功率密度', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 1)

    plt.tight_layout()
    save_path = os.path.join(PROJECT_ROOT, 'figures', '10_weighted_analysis.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n    权重影响图已保存: {save_path}")
    plt.close()

    return results


def main():
    print("\n" + "#"*70)
    print("# 综合任务脚本: 4个用户请求")
    print("#"*70)

    # 运行任务1: 增大区域测试
    result = run_large_region_test()
    pareto_solutions, objectives, polygons, task_points, radar_configs, J, N_bin, ecr_array, j_min_array = result

    if objectives is not None and len(objectives) > 0:
        # 运行任务2: 可视化Pareto前沿
        visualize_pareto_front(pareto_solutions, objectives,
                               os.path.join(PROJECT_ROOT, 'figures', '10_pareto_analysis.png'))

        # 运行任务3: 分析目标函数关系（传入额外数据）
        analyze_objective_relationship(pareto_solutions, objectives, ecr_array, j_min_array)

        # 运行任务4: 权重分析
        weighted_pareto_analysis(pareto_solutions, objectives, polygons, task_points, radar_configs, J, N_bin)
    else:
        print("\n[错误] 未能获得有效的Pareto解")

    print("\n" + "#"*70)
    print("# 所有任务完成")
    print("#"*70)


if __name__ == "__main__":
    main()