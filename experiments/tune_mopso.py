"""
MOPSO 参数调优脚本

系统测试不同参数组合对收敛速度和解质量的影响。

测试维度：
- N_P: 粒子数
- T_max: 迭代次数
- w_strategy: 惯性权重策略
- c_1, c_2: 学习因子
- p_m_base: 变异概率下限
- select_gb: 全局最优选择策略

评估指标：
- 超体积 (Hypervolume)
- Pareto 解数量
- 运行时间
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
import sys
import os
import time
import json
from itertools import product

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, create_normalized_evaluate_function
)
from src.mopso import MOPSO_DT
from src.benchmarks import find_knee_point, get_extreme_points
from src.pareto_visualization import (plot_pareto_front_enhanced,
                             plot_convergence_curve, plot_comprehensive_pareto)
from shapely.geometry import Polygon as ShapelyPolygon


# ============================================================================
# 超体积计算
# ============================================================================

def calculate_hypervolume(objectives, ref_point):
    """
    计算二维 Pareto 前沿的超体积

    超体积 = Pareto 前沿与参考点围成的面积

    Args:
        objectives: (N, 2) 数组，每行 [f1, f2]
        ref_point: 参考点 [ref_f1, ref_f2]，应劣于所有解

    Returns:
        hv: 超体积值
    """
    if len(objectives) == 0:
        return 0.0

    # 按 f1 排序
    sorted_idx = np.argsort(objectives[:, 0])
    sorted_obj = objectives[sorted_idx]

    hv = 0.0
    prev_f1 = 0.0

    for i in range(len(sorted_obj)):
        f1 = sorted_obj[i, 0]
        f2 = sorted_obj[i, 1]

        # 矩形面积 = (f1 - prev_f1) * (ref_f2 - f2)
        width = f1 - prev_f1
        height = ref_point[1] - f2

        if width > 0 and height > 0:
            hv += width * height

        prev_f1 = f1

    return hv


def calculate_spacing(objectives):
    """
    计算 Pareto 前沿的间距指标 (Spacing)

    Spacing 越小，解的分布越均匀

    Args:
        objectives: (N, 2) 数组

    Returns:
        sp: 间距值
    """
    if len(objectives) <= 1:
        return 0.0

    n = len(objectives)
    distances = np.full(n, np.inf)

    for i in range(n):
        for j in range(n):
            if i != j:
                d = np.sum(np.abs(objectives[i] - objectives[j]))
                distances[i] = min(distances[i], d)

    d_mean = np.mean(distances)
    sp = np.sqrt(np.sum((distances - d_mean) ** 2) / (n - 1))
    return sp


# ============================================================================
# 问题实例定义
# ============================================================================

def create_problem_instance(region_size=200, n_radars=10, beta=0.02, grid_size=20):
    """创建固定的问题实例"""
    region = ShapelyPolygon([(0, 0), (region_size, 0),
                             (region_size, region_size), (0, region_size)])

    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)

    task_points = generate_uniform_task_points(region, grid_size=grid_size)

    radar_configs = [
        RadarConfig(P0=0.95, P_min=0.8, beta=beta, is_air=True)
        for _ in range(n_radars)
    ]

    return {
        'region': region,
        'polygons': polygons,
        'codes': codes,
        'n_bits': n_bits,
        'task_points': task_points,
        'radar_configs': radar_configs,
        'J': n_radars,
        'N_bin': max(1, int(np.ceil(np.log2(len(polygons))))),
    }


# ============================================================================
# 单次实验
# ============================================================================

def run_single_experiment(problem, params, seed=42):
    """
    运行单次实验

    Args:
        problem: 问题实例
        params: 算法参数字典
        seed: 随机种子

    Returns:
        result: 包含各项指标的字典
    """
    np.random.seed(seed)

    evaluate_func = create_normalized_evaluate_function(
        problem['task_points'],
        problem['radar_configs'],
        problem['polygons'],
        problem['J'],
        problem['N_bin'],
        J_max_ref=0.001
    )

    mopso = MOPSO_DT(
        J=problem['J'],
        N_bin=problem['N_bin'],
        evaluate_func=evaluate_func,
        N_P=params['N_P'],
        T_max=params['T_max'],
        c_1=params['c_1'],
        c_2=params['c_2'],
        p_c=params.get('p_c', 0.9),
        archive_size=params.get('archive_size', 100),
        verbose=False,
        w_strategy=params.get('w_strategy', 'legacy'),
        p_m_base=params.get('p_m_base', 0.0),
        select_gb=params.get('select_gb', 'random'),
    )

    t0 = time.time()
    archive, stats = mopso.optimize()
    elapsed = time.time() - t0

    # 提取目标值
    if len(archive) > 0:
        objectives = np.array([entry['objectives'] for entry in archive])
        # f1 = 1-ECR (最小化), f2 = J_norm (最小化)
        # 参考点：略差于最差解
        ref_point = [1.1, objectives[:, 1].max() * 1.5 if len(objectives) > 0 else 1.0]
        hv = calculate_hypervolume(objectives, ref_point)
        sp = calculate_spacing(objectives)
        n_solutions = len(archive)
        ecr_range = [1 - objectives[:, 0].max(), 1 - objectives[:, 0].min()]
        j_range = [objectives[:, 1].min(), objectives[:, 1].max()]
    else:
        hv = 0.0
        sp = 0.0
        n_solutions = 0
        ecr_range = [0, 0]
        j_range = [0, 0]

    return {
        'time': elapsed,
        'n_solutions': n_solutions,
        'hypervolume': hv,
        'spacing': sp,
        'ecr_range': ecr_range,
        'j_range': j_range,
        'archive': archive,
        'objectives': objectives if len(archive) > 0 else np.array([]),
    }


# ============================================================================
# 参数网格定义
# ============================================================================

def get_param_grid():
    """定义参数调优网格"""
    param_grid = {
        # 实验1: 粒子数影响
        'particle_count': {
            'N_P': [20, 30, 50, 80],
            'T_max': [100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['legacy'],
            'p_m_base': [0.0],
            'select_gb': ['random'],
        },
        # 实验2: 迭代次数影响
        'iteration_count': {
            'N_P': [50],
            'T_max': [30, 50, 100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['legacy'],
            'p_m_base': [0.0],
            'select_gb': ['random'],
        },
        # 实验3: 惯性权重策略
        'inertia_strategy': {
            'N_P': [50],
            'T_max': [100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['legacy', 'standard', 'adaptive'],
            'p_m_base': [0.0],
            'select_gb': ['random'],
        },
        # 实验4: 学习因子
        'learning_factors': {
            'N_P': [50],
            'T_max': [100],
            'c_1': [1.5, 2.0, 2.5],
            'c_2': [2.0],
            'w_strategy': ['standard'],
            'p_m_base': [0.0],
            'select_gb': ['random'],
        },
        # 实验5: 变异概率
        'mutation_rate': {
            'N_P': [50],
            'T_max': [100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['standard'],
            'p_m_base': [0.0, 0.01, 0.03, 0.05],
            'select_gb': ['random'],
        },
        # 实验6: 全局最优选择策略
        'gb_selection': {
            'N_P': [50],
            'T_max': [100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['standard'],
            'p_m_base': [0.01],
            'select_gb': ['random', 'crowding'],
        },
        # 实验7: 最佳组合对比
        'best_combo': {
            'N_P': [50],
            'T_max': [100],
            'c_1': [2.0], 'c_2': [2.0],
            'w_strategy': ['legacy', 'standard'],
            'p_m_base': [0.0, 0.01],
            'select_gb': ['random', 'crowding'],
        },
    }
    return param_grid


def expand_grid(grid):
    """将参数网格展开为参数字典列表"""
    keys = list(grid.keys())
    values = list(grid.values())
    combos = list(product(*values))
    return [dict(zip(keys, combo)) for combo in combos]


# ============================================================================
# 运行所有实验
# ============================================================================

def run_all_experiments(problem, n_seeds=3):
    """运行所有参数调优实验"""
    param_grid = get_param_grid()
    all_results = {}

    for exp_name, grid in param_grid.items():
        print(f"\n{'='*60}")
        print(f"实验: {exp_name}")
        print(f"{'='*60}")

        param_list = expand_grid(grid)
        results = []

        for i, params in enumerate(param_list):
            seed_results = []
            for seed in range(n_seeds):
                np.random.seed(seed * 1000 + i)
                result = run_single_experiment(problem, params, seed=seed * 1000 + i)
                seed_results.append(result)

            # 取平均
            avg_result = {
                'params': params,
                'time': np.mean([r['time'] for r in seed_results]),
                'n_solutions': np.mean([r['n_solutions'] for r in seed_results]),
                'hypervolume': np.mean([r['hypervolume'] for r in seed_results]),
                'spacing': np.mean([r['spacing'] for r in seed_results]),
                'ecr_range': [
                    np.mean([r['ecr_range'][0] for r in seed_results]),
                    np.mean([r['ecr_range'][1] for r in seed_results])
                ],
                'j_range': [
                    np.mean([r['j_range'][0] for r in seed_results]),
                    np.mean([r['j_range'][1] for r in seed_results])
                ],
                'std_hv': np.std([r['hypervolume'] for r in seed_results]),
                'best_objectives': seed_results[0]['objectives'],
            }

            results.append(avg_result)

            param_str = ', '.join(f'{k}={v}' for k, v in params.items())
            print(f"  [{i+1}/{len(param_list)}] {param_str}")
            print(f"    HV={avg_result['hypervolume']:.6f} ± {avg_result['std_hv']:.6f}, "
                  f"解数={avg_result['n_solutions']:.1f}, "
                  f"时间={avg_result['time']:.1f}s")

        all_results[exp_name] = results

    return all_results


# ============================================================================
# 可视化
# ============================================================================

def plot_particle_count_effect(results, save_dir):
    """粒子数影响分析"""
    data = results['particle_count']
    n_ps = [r['params']['N_P'] for r in data]
    hvs = [r['hypervolume'] for r in data]
    times = [r['time'] for r in data]
    n_sols = [r['n_solutions'] for r in data]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    ax1 = axes[0]
    ax1.plot(n_ps, hvs, 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('粒子数 N_P', fontsize=12)
    ax1.set_ylabel('超体积 (Hypervolume)', fontsize=12)
    ax1.set_title('粒子数 vs 解质量', fontsize=14)
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.plot(n_ps, times, 'r-o', linewidth=2, markersize=8)
    ax2.set_xlabel('粒子数 N_P', fontsize=12)
    ax2.set_ylabel('运行时间 (s)', fontsize=12)
    ax2.set_title('粒子数 vs 运行时间', fontsize=14)
    ax2.grid(True, alpha=0.3)

    ax3 = axes[2]
    ax3.plot(n_ps, n_sols, 'g-o', linewidth=2, markersize=8)
    ax3.set_xlabel('粒子数 N_P', fontsize=12)
    ax3.set_ylabel('Pareto 解数量', fontsize=12)
    ax3.set_title('粒子数 vs 解数量', fontsize=14)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(save_dir, 'tune_particle_count.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  保存: {path}")


def plot_iteration_effect(results, save_dir):
    """迭代次数影响分析"""
    data = results['iteration_count']
    t_maxs = [r['params']['T_max'] for r in data]
    hvs = [r['hypervolume'] for r in data]
    times = [r['time'] for r in data]
    n_sols = [r['n_solutions'] for r in data]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    ax1 = axes[0]
    ax1.plot(t_maxs, hvs, 'b-o', linewidth=2, markersize=8)
    ax1.set_xlabel('迭代次数 T_max', fontsize=12)
    ax1.set_ylabel('超体积', fontsize=12)
    ax1.set_title('迭代次数 vs 解质量', fontsize=14)
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.plot(t_maxs, times, 'r-o', linewidth=2, markersize=8)
    ax2.set_xlabel('迭代次数 T_max', fontsize=12)
    ax2.set_ylabel('运行时间 (s)', fontsize=12)
    ax2.set_title('迭代次数 vs 运行时间', fontsize=14)
    ax2.grid(True, alpha=0.3)

    ax3 = axes[2]
    ax3.plot(t_maxs, n_sols, 'g-o', linewidth=2, markersize=8)
    ax3.set_xlabel('迭代次数 T_max', fontsize=12)
    ax3.set_ylabel('Pareto 解数量', fontsize=12)
    ax3.set_title('迭代次数 vs 解数量', fontsize=14)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(save_dir, 'tune_iteration_count.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  保存: {path}")


def plot_inertia_strategy_comparison(results, save_dir):
    """惯性权重策略对比"""
    data = results['inertia_strategy']
    strategies = [r['params']['w_strategy'] for r in data]
    hvs = [r['hypervolume'] for r in data]
    n_sols = [r['n_solutions'] for r in data]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    colors = ['#2196F3', '#4CAF50', '#FF9800']

    ax1 = axes[0]
    bars = ax1.bar(strategies, hvs, color=colors[:len(strategies)], alpha=0.8)
    ax1.set_ylabel('超体积', fontsize=12)
    ax1.set_title('惯性权重策略 vs 解质量', fontsize=14)
    ax1.grid(True, alpha=0.3, axis='y')

    ax2 = axes[1]
    bars = ax2.bar(strategies, n_sols, color=colors[:len(strategies)], alpha=0.8)
    ax2.set_ylabel('Pareto 解数量', fontsize=12)
    ax2.set_title('惯性权重策略 vs 解数量', fontsize=14)
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    path = os.path.join(save_dir, 'tune_inertia_strategy.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  保存: {path}")


def plot_best_combo_pareto(results, save_dir):
    """最佳组合的 Pareto 前沿对比 — 使用增强可视化，标注拐点"""
    data = results['best_combo']

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, len(data)))

    for i, result in enumerate(data):
        if len(result['best_objectives']) > 0:
            obj = result['best_objectives']
            label = f"w={result['params']['w_strategy']}, p_m={result['params']['p_m_base']}, gb={result['params']['select_gb']}"
            ax.scatter(obj[:, 0], obj[:, 1], c=[colors[i]], s=50, alpha=0.7,
                      edgecolors='black', linewidth=0.5, label=label)

            # 标注每个组合的拐点
            if len(obj) >= 3:
                knee_idx = find_knee_point(obj)
                ax.scatter(obj[knee_idx, 0], obj[knee_idx, 1], c=[colors[i]],
                          s=200, marker='*', edgecolors='black', linewidth=1.0,
                          zorder=10)

    # 用第一个结果演示带拐点标注的增强版本
    if len(data) > 0 and len(data[0]['best_objectives']) > 2:
        best_obj = data[0]['best_objectives']
        best_cov_idx, best_int_idx, knee_idx = get_extreme_points(best_obj)
        for idx, label, color, offset in [
            (best_cov_idx, 'Best f1', 'darkred', (10, 20)),
            (best_int_idx, 'Best f2', 'darkblue', (-50, -25)),
            (knee_idx, 'Knee point', 'darkgreen', (20, -20)),
        ]:
            ax.annotate(f'{label}\n({best_obj[idx, 0]:.4f}, {best_obj[idx, 1]:.4f})',
                        (best_obj[idx, 0], best_obj[idx, 1]),
                        xytext=offset, textcoords='offset points', fontsize=9,
                        arrowprops=dict(arrowstyle='->', color=color, lw=1.2),
                        color=color, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    ax.set_xlabel('f1 = 1 - ECR', fontsize=12)
    ax.set_ylabel('f2 = J_norm', fontsize=12)
    ax.set_title('不同参数组合的 Pareto 前沿 (* = 拐点)', fontsize=14)
    ax.legend(fontsize=8, loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(save_dir, 'tune_pareto_comparison.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  保存: {path}")


def plot_summary_heatmap(results, save_dir):
    """生成参数-性能总结热力图"""
    # 从 best_combo 实验中提取数据
    data = results['best_combo']

    # 构建矩阵：w_strategy × select_gb
    strategies = ['legacy', 'standard']
    gb_methods = ['random', 'crowding']

    hv_matrix = np.zeros((len(strategies), len(gb_methods)))
    time_matrix = np.zeros((len(strategies), len(gb_methods)))

    for result in data:
        params = result['params']
        si = strategies.index(params['w_strategy'])
        gi = gb_methods.index(params['select_gb'])
        hv_matrix[si, gi] = result['hypervolume']
        time_matrix[si, gi] = result['time']

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    ax1 = axes[0]
    im1 = ax1.imshow(hv_matrix, cmap='YlOrRd', aspect='auto')
    ax1.set_xticks(range(len(gb_methods)))
    ax1.set_xticklabels(gb_methods)
    ax1.set_yticks(range(len(strategies)))
    ax1.set_yticklabels(strategies)
    ax1.set_xlabel('选择策略', fontsize=12)
    ax1.set_ylabel('惯性策略', fontsize=12)
    ax1.set_title('超体积热力图', fontsize=14)
    for i in range(len(strategies)):
        for j in range(len(gb_methods)):
            ax1.text(j, i, f'{hv_matrix[i,j]:.4f}', ha='center', va='center', fontsize=12)
    plt.colorbar(im1, ax=ax1)

    ax2 = axes[1]
    im2 = ax2.imshow(time_matrix, cmap='YlGnBu', aspect='auto')
    ax2.set_xticks(range(len(gb_methods)))
    ax2.set_xticklabels(gb_methods)
    ax2.set_yticks(range(len(strategies)))
    ax2.set_yticklabels(strategies)
    ax2.set_xlabel('选择策略', fontsize=12)
    ax2.set_ylabel('惯性策略', fontsize=12)
    ax2.set_title('运行时间热力图 (s)', fontsize=14)
    for i in range(len(strategies)):
        for j in range(len(gb_methods)):
            ax2.text(j, i, f'{time_matrix[i,j]:.1f}', ha='center', va='center', fontsize=12)
    plt.colorbar(im2, ax=ax2)

    plt.tight_layout()
    path = os.path.join(save_dir, 'tune_summary_heatmap.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  保存: {path}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 70)
    print("MOPSO 参数调优实验")
    print("=" * 70)

    # 创建问题实例
    print("\n[1] 创建问题实例 (100km, 5 雷达, beta=0.03)...")
    problem = create_problem_instance(region_size=100, n_radars=5, beta=0.03, grid_size=15)
    print(f"    任务点: {len(problem['task_points'])}")
    print(f"    凸多边形: {len(problem['polygons'])}")
    print(f"    N_bin: {problem['N_bin']}")

    # 运行所有实验
    print("\n[2] 运行参数调优实验...")
    results = run_all_experiments(problem, n_seeds=2)

    # 生成可视化
    save_dir = os.path.join(PROJECT_ROOT, 'figures')
    os.makedirs(save_dir, exist_ok=True)

    print("\n[3] 生成可视化图表...")
    plot_particle_count_effect(results, save_dir)
    plot_iteration_effect(results, save_dir)
    plot_inertia_strategy_comparison(results, save_dir)
    plot_best_combo_pareto(results, save_dir)
    plot_summary_heatmap(results, save_dir)

    # 输出总结
    print("\n" + "=" * 70)
    print("调优结果总结")
    print("=" * 70)

    # 找出最佳组合
    best_combo_data = results['best_combo']
    best_idx = np.argmax([r['hypervolume'] for r in best_combo_data])
    best = best_combo_data[best_idx]

    print(f"\n最佳参数组合:")
    for k, v in best['params'].items():
        print(f"  {k}: {v}")
    print(f"\n  超体积: {best['hypervolume']:.6f} ± {best['std_hv']:.6f}")
    print(f"  Pareto 解数: {best['n_solutions']:.1f}")
    print(f"  运行时间: {best['time']:.1f}s")
    print(f"  ECR 范围: [{best['ecr_range'][0]:.4f}, {best['ecr_range'][1]:.4f}]")
    print(f"  J_min 范围: [{best['j_range'][0]:.8f}, {best['j_range'][1]:.8f}]")

    # 拐点信息
    if len(best['best_objectives']) >= 3:
        knee_idx = find_knee_point(best['best_objectives'])
        knee_obj = best['best_objectives'][knee_idx]
        real_ecr = 1.0 - knee_obj[0]
        print(f"  拐点 (Knee): f1={knee_obj[0]:.4f}, f2={knee_obj[1]:.6f}")
        print(f"            ECR={real_ecr:.4f}, J_norm={knee_obj[1]:.6f}")

    # 保存结果
    results_file = os.path.join(save_dir, 'tune_results.json')
    save_data = {}
    for exp_name, exp_results in results.items():
        save_data[exp_name] = []
        for r in exp_results:
            entry = {k: v for k, v in r.items() if k not in ('best_objectives',)}
            entry['ecr_range'] = [float(x) for x in entry['ecr_range']]
            entry['j_range'] = [float(x) for x in entry['j_range']]
            save_data[exp_name].append(entry)

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\n详细结果已保存: {results_file}")

    print("\n" + "=" * 70)
    print("调优实验完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
