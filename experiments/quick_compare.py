"""
快速A/B对比：原始MOPSO vs 改进MOPSO
小规模问题 + 可视化输出
"""
import numpy as np
import matplotlib.pyplot as plt
import time, sys, os

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


def run_config(name, w_strategy, p_m_base, select_gb):
    """运行单个配置并返回指标和原始数据"""
    print(f"  Running {name}...", end=' ', flush=True)

    region = ShapelyPolygon([(0, 0), (200, 0), (200, 200), (0, 200)])
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)

    radar_configs = [
        RadarConfig(P0=0.9, P_min=0.8, beta=0.03, is_air=True)
        for _ in range(8)
    ]
    task_points = generate_uniform_task_points(region, grid_size=10)

    J, N_bin = 8, max(1, int(np.ceil(np.log2(len(polygons)))))
    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.005
    )

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=20, T_max=30, c_1=2.0, c_2=2.0, p_c=0.9,
        archive_size=50, verbose=False,
        w_strategy=w_strategy, p_m_base=p_m_base, select_gb=select_gb
    )

    t0 = time.time()
    archive, stats = mopso.optimize()
    elapsed = time.time() - t0
    print(f"done ({elapsed:.1f}s, {len(archive)} solutions)")

    if len(archive) == 0:
        return {'name': name, 'n_solutions': 0, 'time': elapsed, 'error': 'no solutions'}

    objectives = np.array([e['objectives'] for e in archive])

    # 计算实际 ECR/J_min 并保存每个解的详细信息
    solutions_data = []
    ecr_vals, j_vals = [], []
    for entry in archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        cont = sol[:, :2].flatten()
        bin_ = sol[:, 2:2+N_bin]
        pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
        ecr = calculate_ecr(pos, task_points, radar_configs,
                            convex_polygons=polygons, binary_codes=bin_,
                            continuous_coords=cont.reshape(J, 2))
        jm = calculate_jamming_density(pos, task_points, radar_configs,
                                       convex_polygons=polygons, binary_codes=bin_,
                                       continuous_coords=cont.reshape(J, 2))
        ecr_vals.append(ecr)
        j_vals.append(jm)
        solutions_data.append({
            'positions': pos,
            'ecr': ecr, 'j_min': jm,
            'objectives': entry['objectives'].copy()
        })

    ecr_arr = np.array(ecr_vals)
    j_arr = np.array(j_vals)

    # 超体积
    sorted_idx = np.argsort(objectives[:, 0])
    f1_sorted = objectives[sorted_idx, 0]
    f2_sorted = objectives[sorted_idx, 1]
    hv = 0.0
    for k in range(1, len(f1_sorted)):
        hv += (f1_sorted[k] - f1_sorted[k-1]) * (1 - f2_sorted[k])
    hv += (1 - f1_sorted[-1]) * (1 - f2_sorted[-1])

    # 拐点
    knee_idx = find_knee_point(objectives) if len(objectives) >= 3 else None

    return {
        'name': name,
        'n_solutions': len(archive),
        'time': elapsed,
        'hypervolume': float(hv),
        'f1_range': float(objectives[:, 0].max() - objectives[:, 0].min()),
        'f2_range': float(objectives[:, 1].max() - objectives[:, 1].min()),
        'ecr_range': [float(ecr_arr.min()), float(ecr_arr.max())],
        'j_range': [float(j_arr.min()), float(j_arr.max())],
        'correlation': float(np.corrcoef(ecr_arr, j_arr)[0, 1]) if len(archive) > 2 else 0,
        'knee_idx': knee_idx,
        'objectives': objectives,
        'ecr_array': ecr_arr,
        'j_array': j_arr,
        'solutions_data': solutions_data,
        'polygons': polygons,
        'task_points': task_points,
        'radar_configs': radar_configs,
        'J': J, 'N_bin': N_bin
    }


def visualize_comparison(baseline, improved):
    """生成综合对比可视化"""
    save_dir = os.path.join(PROJECT_ROOT, 'figures')
    os.makedirs(save_dir, exist_ok=True)

    fig = plt.figure(figsize=(18, 12))

    # ========== 图1: Pareto前沿对比 (左上) ==========
    ax1 = fig.add_subplot(2, 3, 1)
    colors_b = plt.cm.Blues(np.linspace(0.4, 1, baseline['n_solutions']))
    colors_i = plt.cm.Oranges(np.linspace(0.4, 1, improved['n_solutions']))

    ax1.scatter(baseline['objectives'][:, 0], baseline['objectives'][:, 1],
                c=colors_b, s=100, alpha=0.8, edgecolors='navy', linewidth=1,
                label=f"BASELINE ({baseline['n_solutions']} sols)", zorder=3)
    ax1.scatter(improved['objectives'][:, 0], improved['objectives'][:, 1],
                c=colors_i, s=100, alpha=0.8, edgecolors='darkred', linewidth=1,
                label=f"IMPROVED ({improved['n_solutions']} sols)", zorder=3)

    # 拐点标注
    for data, color, offset in [
        (baseline, 'navy', (-40, -30)),
        (improved, 'darkred', (30, 30))
    ]:
        if data['knee_idx'] is not None:
            ki = data['knee_idx']
            ax1.scatter(data['objectives'][ki, 0], data['objectives'][ki, 1],
                        c='gold', s=200, marker='*', edgecolors='black', zorder=5)
            ax1.annotate(f"Knee\nECR={1-data['objectives'][ki,0]:.3f}",
                         (data['objectives'][ki, 0], data['objectives'][ki, 1]),
                         xytext=offset, textcoords='offset points', fontsize=8,
                         color=color, fontweight='bold',
                         arrowprops=dict(arrowstyle='->', color=color, lw=1),
                         bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.9))

    ax1.set_xlabel('f1 = 1 - ECR', fontsize=11)
    ax1.set_ylabel('f2 = J_norm', fontsize=11)
    ax1.set_title('Pareto Front Comparison', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9, loc='upper right')
    ax1.grid(True, alpha=0.3)

    # ========== 图2: ECR vs J_min 真实目标空间 (中上) ==========
    ax2 = fig.add_subplot(2, 3, 2)
    ax2.scatter(baseline['ecr_array'], baseline['j_array'],
                c='steelblue', s=80, alpha=0.7, edgecolors='navy', linewidth=0.5,
                label='BASELINE')
    ax2.scatter(improved['ecr_array'], improved['j_array'],
                c='coral', s=80, alpha=0.7, edgecolors='darkred', linewidth=0.5,
                label='IMPROVED')

    # 拐点
    for data, color in [(baseline, 'navy'), (improved, 'darkred')]:
        if data['knee_idx'] is not None:
            ki = data['knee_idx']
            ax2.scatter(data['ecr_array'][ki], data['j_array'][ki],
                        c='gold', s=150, marker='*', edgecolors='black', zorder=5)

    ax2.set_xlabel('ECR', fontsize=11)
    ax2.set_ylabel('J_min (W/m^2)', fontsize=11)
    ax2.set_title('ECR vs J_min (Physical Space)', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    # ========== 图3: 部署方案对比 - BASELINE (中中) ==========
    ax3 = fig.add_subplot(2, 3, 4)
    _plot_deployment(ax3, baseline, 'BASELINE Deployment (Best ECR)')

    # ========== 图4: 部署方案对比 - IMPROVED (中右) ==========
    ax4 = fig.add_subplot(2, 3, 5)
    _plot_deployment(ax4, improved, 'IMPROVED Deployment (Best ECR)')

    # ========== 图5: 指标对比雷达/条形图 (右上) ==========
    ax5 = fig.add_subplot(2, 3, 3)
    metrics = ['Solutions', 'Hypervolume', 'f1 Range', 'f2 Range', 'ECR Max', 'Speed']
    b_vals = [
        baseline['n_solutions'],
        baseline['hypervolume'],
        baseline['f1_range'],
        baseline['f2_range'],
        baseline['ecr_range'][1],
        1.0 / baseline['time']  # speed = 1/time
    ]
    i_vals = [
        improved['n_solutions'],
        improved['hypervolume'],
        improved['f1_range'],
        improved['f2_range'],
        improved['ecr_range'][1],
        1.0 / improved['time']
    ]
    # 归一化到 baseline=1.0
    b_norm = np.ones(len(b_vals))
    i_norm = np.array([i_vals[k] / b_vals[k] if b_vals[k] > 1e-9 else 1.0 for k in range(len(b_vals))])

    x = np.arange(len(metrics))
    width = 0.35
    bars1 = ax5.bar(x - width/2, b_norm, width, color='steelblue', alpha=0.8,
                    edgecolor='navy', label='BASELINE')
    bars2 = ax5.bar(x + width/2, i_norm, width, color='coral', alpha=0.8,
                    edgecolor='darkred', label='IMPROVED')
    ax5.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    ax5.set_xticks(x)
    ax5.set_xticklabels(metrics, fontsize=9)
    ax5.set_ylabel('Relative to BASELINE', fontsize=10)
    ax5.set_title('Performance Improvement Multiplier', fontsize=13, fontweight='bold')
    ax5.legend(fontsize=9)

    # 在柱子上标注数值
    for bar, val in zip(bars2, i_norm):
        if val > 1.01:
            ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                     f'{val:.2f}x', ha='center', va='bottom', fontsize=8, fontweight='bold', color='darkred')

    # ========== 图6: 目标分布直方图 (右下) ==========
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.hist(baseline['ecr_array'], bins=8, alpha=0.6, color='steelblue',
             edgecolor='navy', label='BASELINE ECR')
    ax6.hist(improved['ecr_array'], bins=8, alpha=0.6, color='coral',
             edgecolor='darkred', label='IMPROVED ECR')
    ax6.set_xlabel('ECR', fontsize=11)
    ax6.set_ylabel('Count', fontsize=11)
    ax6.set_title('ECR Distribution Comparison', fontsize=13, fontweight='bold')
    ax6.legend(fontsize=9)

    plt.tight_layout(pad=2)
    save_path = os.path.join(save_dir, 'quick_compare_results.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n  Figure saved: {save_path}")
    plt.close()


def _plot_deployment(ax, data, title):
    """绘制单个部署方案"""
    polygons = data['polygons']
    task_points = data['task_points']

    for poly in polygons:
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.2, color='lightblue', edgecolor='blue', linewidth=0.5)

    tx = [t.x for t in task_points]
    ty = [t.y for t in task_points]
    ax.scatter(tx, ty, c='gray', s=2, alpha=0.3)

    # 最佳ECR解
    best_idx = np.argmax(data['ecr_array'])
    pos = data['solutions_data'][best_idx]['positions']
    ax.scatter(pos[:, 0], pos[:, 1], c='red', s=120, marker='^',
               edgecolors='black', linewidth=1.5, zorder=5)
    for j, (px, py) in enumerate(pos):
        ax.annotate(f'R{j+1}', (px, py), textcoords="offset points",
                    xytext=(4, 4), fontsize=7, fontweight='bold')

    ecr_best = data['ecr_array'][best_idx]
    jm_best = data['j_array'][best_idx]
    ax.set_xlabel('X (km)')
    ax.set_ylabel('Y (km)')
    ax.set_title(f"{title}\nECR={ecr_best:.4f}, J_min={jm_best:.4e}", fontsize=11, fontweight='bold')
    ax.set_xlim(-10, 210)
    ax.set_ylim(-10, 210)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)


def main():
    print("\n" + "#"*60)
    print("# Quick A/B Comparison: Baseline vs Improved MOPSO")
    print("# Problem: 200km x 200km, 8 radars, N_P=20, T_max=30")
    print("#"*60)

    baseline = run_config("BASELINE", 'legacy', 0.0, 'random')
    improved = run_config("IMPROVED", 'standard', 0.01, 'crowding')

    # 数值对比表格
    b, i = baseline, improved
    print("\n" + "="*70)
    print("  Comparison Results")
    print("="*70)
    print(f"{'Metric':<28} {'BASELINE':>18} {'IMPROVED':>18} {'Change':>12}")
    print("-"*70)

    rows = [
        ('Pareto Solutions', b['n_solutions'], i['n_solutions'], True),
        ('Runtime (s)', b['time'], i['time'], False),
        ('Hypervolume', b['hypervolume'], i['hypervolume'], True),
        ('f1 Range (diversity)', b['f1_range'], i['f1_range'], True),
        ('f2 Range (diversity)', b['f2_range'], i['f2_range'], True),
        ('ECR Max', b['ecr_range'][1], i['ecr_range'][1], True),
        ('ECR Min', b['ecr_range'][0], i['ecr_range'][0], False),
        ('J_min Min', b['j_range'][0], i['j_range'][0], False),
        ('ECR-J Correlation', b['correlation'], i['correlation'], None),
    ]
    for label, bv, iv, higher_better in rows:
        delta = iv - bv if bv is not None else 0
        if isinstance(bv, float) and abs(bv) > 1e-9:
            pct = delta / abs(bv) * 100
            direction = '[+]' if delta > 0 else '[-]' if delta < 0 else '[~]'
            flag = ' [OK]' if ((higher_better and delta > 0) or (higher_better is False and delta < 0)) else ''
            if abs(bv) < 1e-4:
                print(f"{label:<28} {bv:>18.6e} {iv:>18.6e} {direction} {abs(pct):>5.1f}%{flag}")
            else:
                print(f"{label:<28} {bv:>18.4f} {iv:>18.4f} {direction} {abs(pct):>5.1f}%{flag}")
        elif isinstance(bv, int):
            pct = delta / bv * 100 if bv > 0 else 0
            direction = '[+]' if delta > 0 else '[-]' if delta < 0 else '[~]'
            flag = ' [OK]' if delta > 0 else ''
            print(f"{label:<28} {bv:>18d} {iv:>18d} {direction} {abs(pct):>5.1f}%{flag}")
        else:
            print(f"{label:<28} {str(bv):>18} {str(iv):>18}")

    print("-"*70)
    print("  [OK] = Improvement direction favorable\n")

    if b['knee_idx'] is not None and i['knee_idx'] is not None:
        print(f"  Knee point comparison:")
        print(f"    BASELINE - ECR={1-b['objectives'][b['knee_idx'],0]:.4f}, "
              f"J_min={b['j_array'][b['knee_idx']]:.6e}")
        print(f"    IMPROVED - ECR={1-i['objectives'][i['knee_idx'],0]:.4f}, "
              f"J_min={i['j_array'][i['knee_idx']]:.6e}")

    # 生成可视化
    print("\n  Generating visualization...")
    visualize_comparison(baseline, improved)

    print("\n" + "#"*60)
    print("# Comparison Complete")
    print("#"*60)


if __name__ == "__main__":
    main()
