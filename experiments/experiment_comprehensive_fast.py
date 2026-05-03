"""
快速综合任务脚本：处理4个用户请求（优化版）
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.coordinate_transform import transform_coordinates, is_convex_polygon
from src.evaluation import (
    RadarConfig, TaskPoint, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, evaluate_deployment_normalized,
    create_normalized_evaluate_function
)
from src.mopso import MOPSO_DT

from shapely.geometry import Polygon as ShapelyPolygon


def run_fast_test():
    """快速测试版本"""
    print("\n" + "="*70)
    print("快速测试: 100km x 100km, 5 radars (缩减参数)")
    print("="*70)

    # 创建区域
    region = ShapelyPolygon([(0, 0), (100, 0), (100, 100), (0, 100)])

    # 区域分解
    print("\n[1] 区域分解...")
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    print(f"    分解得到 {len(polygons)} 个凸多边形")

    # 雷达配置
    radar_configs = [RadarConfig(P0=0.95, P_min=0.8, beta=0.01, is_air=True) for _ in range(5)]

    # 生成任务点
    print("\n[2] 生成任务点...")
    task_points = generate_uniform_task_points(region, grid_size=15)
    print(f"    生成 {len(task_points)} 个任务点")

    # MOPSO优化（减少迭代和粒子数）
    print("\n[3] MOPSO优化 (快速模式)...")
    J = 5
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    print(f"    J={J}, N_bin={N_bin}, 粒子=30, 迭代=30")

    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.001
    )

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=30, T_max=30, verbose=False
    )

    pareto_archive, stats = mopso.optimize()

    print(f"\n[4] 优化结果:")
    print(f"    Pareto解数量: {len(pareto_archive)}")

    if len(pareto_archive) == 0:
        print("    [错误] 没有找到Pareto解")
        return None, None, None, None, None, None, None, None, None, None

    # 提取解
    pareto_solutions = []
    objectives_list = []
    ecr_list = []
    j_min_list = []

    for entry in pareto_archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        pareto_solutions.append(sol)
        objectives_list.append(entry['objectives'])

        # 计算实际的ECR和J_min
        continuous = sol[:, :2].flatten()
        binary = sol[:, 2:2+N_bin]
        positions = decode_particle(continuous, binary, J, N_bin, polygons)
        positions_array = np.array(positions)

        ecr = calculate_ecr(positions_array, task_points, radar_configs,
                           convex_polygons=polygons, binary_codes=binary,
                           continuous_coords=continuous.reshape(J, 2))
        j_min = calculate_jamming_density(positions_array, task_points, radar_configs,
                                         convex_polygons=polygons, binary_codes=binary,
                                         continuous_coords=continuous.reshape(J, 2))
        ecr_list.append(ecr)
        j_min_list.append(j_min)

    objectives = np.array(objectives_list)
    ecr_array = np.array(ecr_list)
    j_min_array = np.array(j_min_list)

    print(f"    f1范围: [{objectives[:,0].min():.4f}, {objectives[:,0].max():.4f}]")
    print(f"    f2范围: [{objectives[:,1].min():.4f}, {objectives[:,1].max():.4f}]")
    print(f"    ECR范围: [{ecr_array.min():.4f}, {ecr_array.max():.4f}]")
    print(f"    J_min范围: [{j_min_array.min():.8f}, {j_min_array.max():.8f}]")

    return pareto_solutions, objectives, ecr_array, j_min_array, polygons, task_points, radar_configs, J, N_bin


def visualize_pareto_front(pareto_solutions, objectives, save_path=None):
    """任务2: 可视化pareto前沿分布"""
    print("\n" + "="*70)
    print("任务2: 可视化Pareto前沿分布")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) == 0:
        print("    [警告] 没有Pareto解可可视化")
        return

    print(f"    可视化 {len(pareto_solutions)} 个Pareto解")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 图1: Pareto前沿
    ax1 = axes[0]
    ax1.scatter(objectives[:, 0], objectives[:, 1], c='blue', s=100, alpha=0.7, edgecolors='black')
    ax1.set_xlabel('f1 = 1 - ECR', fontsize=12)
    ax1.set_ylabel('f2 = J_norm', fontsize=12)
    ax1.set_title('Pareto前沿分布', fontsize=14)
    ax1.grid(True, alpha=0.3)

    # 图2: 分布直方图
    ax2 = axes[1]
    ax2.hist(objectives[:, 0], bins=min(10, len(pareto_solutions)), alpha=0.7, label='f1 (1-ECR)', color='blue')
    ax2.set_xlabel('目标函数值', fontsize=12)
    ax2.set_ylabel('频数', fontsize=12)
    ax2.set_title('f1分布', fontsize=14)
    ax2.legend()

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"    图像已保存: {save_path}")
    plt.close()


def analyze_objective_relationship(pareto_solutions, objectives, ecr_array, j_min_array):
    """任务3: 分析两个目标函数的关系"""
    print("\n" + "="*70)
    print("任务3: 分析两个目标函数的关系")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) < 3:
        print("    [警告] Pareto解数量不足")
        return

    print(f"    分析 {len(pareto_solutions)} 个Pareto解")

    correlation = np.corrcoef(ecr_array, j_min_array)[0, 1]

    print("\n    === 统计分析 ===")
    print(f"    ECR范围: [{ecr_array.min():.4f}, {ecr_array.max():.4f}]")
    print(f"    J_min范围: [{j_min_array.min():.8f}, {j_min_array.max():.8f}]")
    print(f"    ECR与J_min的相关系数: {correlation:.4f}")

    if correlation < -0.5:
        print("    结论: 强负相关 - 覆盖与干扰压制存在矛盾")
    elif correlation < 0:
        print("    结论: 中等负相关 - 需要权衡")
    else:
        print("    结论: 正相关或不相关 - 可同时优化")

    # 可视化
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    ax1 = axes[0]
    ax1.scatter(ecr_array, j_min_array, c='blue', s=80, alpha=0.7)
    ax1.set_xlabel('ECR', fontsize=12)
    ax1.set_ylabel('J_min', fontsize=12)
    ax1.set_title(f'ECR vs J_min (相关系数={correlation:.3f})', fontsize=12)
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.scatter(ecr_array, objectives[:, 0], c='red', s=80, alpha=0.7)
    ax2.set_xlabel('ECR', fontsize=12)
    ax2.set_ylabel('f1 = 1-ECR', fontsize=12)
    ax2.set_title('ECR vs f1', fontsize=12)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = os.path.join(PROJECT_ROOT, 'figures', '11_objective_relationship.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n    关系图已保存: {save_path}")
    plt.close()


def weighted_pareto_analysis(pareto_solutions, objectives, ecr_array, j_min_array):
    """任务4: 权重综合分析"""
    print("\n" + "="*70)
    print("任务4: 权重综合Pareto解分析")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) < 2:
        print("    [警告] Pareto解数量不足")
        return

    weights = [(0.9, 0.1), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.1, 0.9)]

    print("\n    权重 (w1,w2) | 综合目标 | ECR | J_min")
    print("    " + "-"*50)

    results = []
    for w1, w2 in weights:
        weighted_obj = w1 * objectives[:, 0] + w2 * objectives[:, 1]
        best_idx = np.argmin(weighted_obj)

        print(f"    ({w1:.1f}, {w2:.1f})        | {weighted_obj[best_idx]:.6f}  | {ecr_array[best_idx]:.4f} | {j_min_array[best_idx]:.8f}")

        results.append({'weights': (w1, w2), 'ecr': ecr_array[best_idx], 'j_min': j_min_array[best_idx]})

    # 可视化权重影响
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    w_labels = [w[0] for w in weights]
    ecr_vals = [r['ecr'] for r in results]
    j_vals = [r['j_min'] for r in results]

    ax1 = axes[0]
    ax1.plot(w_labels, ecr_vals, 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('w1 (ECR权重)', fontsize=12)
    ax1.set_ylabel('ECR', fontsize=12)
    ax1.set_title('权重 vs ECR', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 1)

    ax2 = axes[1]
    ax2.plot(w_labels, j_vals, 'r-o', linewidth=2, markersize=8)
    ax2.set_xlabel('w1 (ECR权重)', fontsize=12)
    ax2.set_ylabel('J_min', fontsize=12)
    ax2.set_title('权重 vs J_min', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 1)

    plt.tight_layout()
    save_path = os.path.join(PROJECT_ROOT, 'figures', '12_weighted_analysis.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n    权重影响图已保存: {save_path}")
    plt.close()

    return results


def main():
    print("\n" + "#"*70)
    print("# 综合任务脚本: 4个用户请求 (快速版)")
    print("#"*70)

    result = run_fast_test()

    if result[0] is None:
        print("\n[错误] 测试失败")
        return

    pareto_solutions, objectives, ecr_array, j_min_array, polygons, task_points, radar_configs, J, N_bin = result

    # 任务2: 可视化Pareto前沿
    visualize_pareto_front(pareto_solutions, objectives,
                          os.path.join(PROJECT_ROOT, 'figures', '10_pareto_front.png'))

    # 任务3: 分析目标函数关系
    analyze_objective_relationship(pareto_solutions, objectives, ecr_array, j_min_array)

    # 任务4: 权重分析
    weighted_pareto_analysis(pareto_solutions, objectives, ecr_array, j_min_array)

    print("\n" + "#"*70)
    print("# 所有任务完成")
    print("#"*70)


if __name__ == "__main__":
    main()