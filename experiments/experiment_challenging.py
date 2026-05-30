"""
挑战性场景测试 - 目标是在更难的问题上产生更多样的Pareto解
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os
import argparse
import json

# Fix GBK encoding for emoji in paths
sys.stdout.reconfigure(encoding='utf-8')

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig, TaskPoint, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, create_normalized_evaluate_function
)
from src.mopso import MOPSO_DT
from src.benchmarks import find_knee_point, get_extreme_points

from shapely.geometry import Polygon as ShapelyPolygon


def save_figure(fig, png_path, dpi=150):
    fig.savefig(png_path, dpi=dpi, bbox_inches='tight')
    pdf_path = os.path.splitext(png_path)[0] + '.pdf'
    fig.savefig(pdf_path, bbox_inches='tight')


def _plot_sorted_front(ax, x_values, y_values, *, color='#2C3E50', label='Pareto前沿'):
    """Connect Pareto points in objective order for paper-style front visualization."""
    x_values = np.asarray(x_values, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    if len(x_values) < 2:
        return
    order = np.argsort(x_values)
    ax.plot(
        x_values[order],
        y_values[order],
        color=color,
        linewidth=1.6,
        alpha=0.85,
        label=label,
        zorder=2,
    )


def run_challenging_test():
    """更具挑战性的场景"""
    np.random.seed(2026)

    print("\n" + "="*70)
    print("挑战性场景: 200km x 200km, 8 radars, beta=0.03 (更难覆盖)")
    print("随机种子: 2026")
    print("="*70)

    # 创建大区域
    region = ShapelyPolygon([(0, 0), (200, 0), (200, 200), (0, 200)])

    # 区域分解
    print("\n[1] 区域分解...")
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    print(f"    分解得到 {len(polygons)} 个凸多边形")

    # 使用更大的beta使覆盖更难（更少的 radars 更稀疏）
    radar_configs = [
        RadarConfig(P0=0.9, P_min=0.8, beta=0.03, is_air=True)
        for _ in range(8)
    ]

    # 生成任务点
    print("\n[2] 生成任务点...")
    task_points = generate_uniform_task_points(region, grid_size=15)
    print(f"    生成 {len(task_points)} 个任务点")

    # MOPSO优化
    print("\n[3] MOPSO优化...")
    J = 8
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    print(f"    J={J}, N_bin={N_bin}, 粒子=50, 迭代=80")

    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.005
    )

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=50, T_max=80, verbose=False,
        w_strategy='standard', p_m_base=0.01, select_gb='crowding'
    )

    pareto_archive, stats = mopso.optimize()

    print(f"\n[4] 优化结果:")
    print(f"    Pareto解数量: {len(pareto_archive)}")

    if len(pareto_archive) == 0:
        print("    [错误] 没有找到Pareto解")
        return None

    # 提取解
    pareto_solutions = []
    objectives_list = []
    ecr_list = []
    j_min_list = []

    for entry in pareto_archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        pareto_solutions.append(sol)
        objectives_list.append(entry['objectives'])

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

    # 拐点检测
    if len(objectives) >= 3:
        knee_idx = find_knee_point(objectives)
        print(f"    拐点 (Knee): ECR={1-objectives[knee_idx,0]:.4f}, "
              f"J_norm={objectives[knee_idx,1]:.6f}")

    return pareto_solutions, objectives, ecr_array, j_min_array


def visualize_results(pareto_solutions, objectives, ecr_array, j_min_array, figure_dir=None):
    """可视化所有结果"""
    print("\n" + "="*70)
    print("可视化结果")
    print("="*70)

    if pareto_solutions is None or len(pareto_solutions) == 0:
        return
    if figure_dir is None:
        figure_dir = os.path.join(PROJECT_ROOT, 'figures')
    os.makedirs(figure_dir, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 图1: Pareto前沿（物理指标）
    ax1 = axes[0, 0]
    _plot_sorted_front(ax1, ecr_array, j_min_array)
    ax1.scatter(ecr_array, j_min_array, c='blue', s=80, alpha=0.7,
                edgecolors='black', zorder=3)
    ax1.set_xlabel('ECR', fontsize=12)
    ax1.set_ylabel(r'$J_{\min}$', fontsize=12)
    ax1.set_title(f'ECR-$J_{{\\min}}$前沿 (共{len(pareto_solutions)}个解)', fontsize=14)
    ax1.grid(True, alpha=0.3)
    ax1.legend(frameon=False, fontsize=9)

    # 图2: ECR vs J_min (真实目标)
    ax2 = axes[0, 1]
    _plot_sorted_front(ax2, ecr_array, j_min_array)
    scatter = ax2.scatter(ecr_array, j_min_array, c=objectives[:, 0], s=80,
                          cmap='viridis', alpha=0.7, zorder=3)
    ax2.set_xlabel('ECR', fontsize=12)
    ax2.set_ylabel('J_min (真实干扰功率)', fontsize=12)
    ax2.set_title('ECR vs J_min (颜色=f1值)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.legend(frameon=False, fontsize=9)
    plt.colorbar(scatter, ax=ax2, label='f1')

    # 图3: ECR分布直方图
    ax3 = axes[1, 0]
    ax3.hist(ecr_array, bins=min(20, len(np.unique(ecr_array))), alpha=0.7, color='green', edgecolor='black')
    ax3.set_xlabel('ECR', fontsize=12)
    ax3.set_ylabel('频数', fontsize=12)
    ax3.set_title(f'ECR分布 (范围: {ecr_array.min():.3f}-{ecr_array.max():.3f})', fontsize=14)

    # 图4: 相关性分析
    ax4 = axes[1, 1]
    correlation = np.corrcoef(ecr_array, j_min_array)[0, 1]
    _plot_sorted_front(ax4, ecr_array, j_min_array)
    ax4.scatter(ecr_array, j_min_array, c='purple', s=80, alpha=0.7, zorder=3)
    ax4.set_xlabel('ECR', fontsize=12)
    ax4.set_ylabel('J_min', fontsize=12)
    ax4.set_title(f'ECR vs J_min (相关系数: {correlation:.3f})', fontsize=14)
    ax4.grid(True, alpha=0.3)
    ax4.legend(frameon=False, fontsize=9)

    plt.tight_layout()
    save_path = os.path.join(figure_dir, '13_challenging_scene.png')
    save_figure(fig, save_path)
    print(f"    综合结果图已保存: {save_path}")
    plt.close()

    # 打印相关性结论
    print(f"\n    相关性分析:")
    if abs(correlation) < 0.3:
        print(f"    相关系数={correlation:.3f} -> 弱相关 (可以同时优化)")
    elif correlation < -0.5:
        print(f"    相关系数={correlation:.3f} -> 强负相关 (需要权衡)")
    else:
        print(f"    相关系数={correlation:.3f} -> 中等相关")

    return correlation


def save_result_summary(pareto_solutions, objectives, ecr_array, j_min_array, output_dir):
    """Save a compact JSON summary for staged thesis review."""
    if output_dir is None:
        return
    os.makedirs(output_dir, exist_ok=True)

    objectives = np.asarray(objectives, dtype=float)
    ecr_array = np.asarray(ecr_array, dtype=float)
    j_min_array = np.asarray(j_min_array, dtype=float)
    correlation = None
    if len(ecr_array) > 2:
        correlation = float(np.corrcoef(ecr_array, j_min_array)[0, 1])
    knee_idx = None
    if len(objectives) >= 3:
        knee_idx = int(find_knee_point(objectives))

    payload = {
        "scenario": "challenging_scene",
        "n_solutions": int(len(ecr_array)),
        "ecr_min": float(ecr_array.min()) if len(ecr_array) else None,
        "ecr_max": float(ecr_array.max()) if len(ecr_array) else None,
        "j_min_min": float(j_min_array.min()) if len(j_min_array) else None,
        "j_min_max": float(j_min_array.max()) if len(j_min_array) else None,
        "correlation": correlation,
        "knee_index": knee_idx,
        "ecr_values": ecr_array.tolist(),
        "j_min_values": j_min_array.tolist(),
        "objectives": objectives.tolist(),
        "n_archived_solutions": int(len(pareto_solutions)),
    }

    path = os.path.join(output_dir, "challenging_scene_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"    Summary saved: {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--figure-dir", default=os.path.join(PROJECT_ROOT, 'figures'))
    args = parser.parse_args()

    print("\n" + "#"*70)
    print("# 挑战性场景测试 - 产生更多样的Pareto解")
    print("#"*70)

    result = run_challenging_test()

    if result is None:
        print("\n[错误] 测试失败")
        return

    pareto_solutions, objectives, ecr_array, j_min_array = result

    # 可视化
    save_result_summary(pareto_solutions, objectives, ecr_array, j_min_array, args.output_dir)
    visualize_results(pareto_solutions, objectives, ecr_array, j_min_array, args.figure_dir)

    print("\n" + "#"*70)
    print("# 测试完成")
    print("#"*70)


if __name__ == "__main__":
    main()
