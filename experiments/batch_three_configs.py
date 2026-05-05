"""
批量对比实验：三种配置在 1000km x 1000km 区域下的效果
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time, sys, os, json

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
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
from src.benchmarks import get_extreme_points
from shapely.geometry import Polygon as ShapelyPolygon

SAVE_DIR = os.path.join(PROJECT_ROOT, 'figures')
os.makedirs(SAVE_DIR, exist_ok=True)

CONFIGS = [
    {
        'name': 'A_Fast',
        'label': 'A: beta=0.003, J=60',
        'J': 60, 'N_P': 60, 'T_max': 60,
        'beta': 0.003, 'P0': 0.9, 'P_min': 0.75,
        'grid_size': 40,
    },
    {
        'name': 'B_Standard',
        'label': 'B: beta=0.004, J=100',
        'J': 100, 'N_P': 80, 'T_max': 80,
        'beta': 0.004, 'P0': 0.9, 'P_min': 0.75,
        'grid_size': 40,
    },
    {
        'name': 'C_Challenging',
        'label': 'C: beta=0.005, J=150',
        'J': 150, 'N_P': 80, 'T_max': 100,
        'beta': 0.005, 'P0': 0.9, 'P_min': 0.75,
        'grid_size': 40,
    },
]

# 复杂区域：1000x1000 外框 + 5个孔洞
HOLES = [
    [(400, 400), (600, 400), (600, 600), (400, 600)],   # 中心禁区
    [(50, 50), (180, 80), (200, 200), (80, 220)],        # 左下湖泊
    [(750, 700), (920, 720), (900, 900), (720, 880)],    # 右上禁区
    [(100, 700), (300, 680), (280, 880), (120, 900)],    # 左上山区
    [(650, 150), (850, 100), (880, 300), (700, 320)],    # 右下河流
]

REGION_SIZE = 1000

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        print(*(str(a).encode('ascii', errors='replace').decode('ascii') for a in args), **kwargs)


def run_config(cfg):
    """运行单个配置，返回结果字典"""
    safe_print(f"\n{'='*70}")
    safe_print(f"  {cfg['label']}")
    safe_print(f"{'='*70}")

    outer = [(0, 0), (REGION_SIZE, 0), (REGION_SIZE, REGION_SIZE), (0, REGION_SIZE)]
    region = ShapelyPolygon(outer, HOLES)

    # 1. 区域分解
    safe_print("  [1] Region decomposition...", end=' ', flush=True)
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    safe_print(f"{len(polygons)} polygons, N_bin={N_bin}")

    # 2. 配置
    J = cfg['J']
    radar_configs = [RadarConfig(P0=cfg['P0'], P_min=cfg['P_min'], beta=cfg['beta'], is_air=True) for _ in range(J)]
    task_points = generate_uniform_task_points(region, grid_size=cfg['grid_size'])
    eff_range = np.log(cfg['P0'] / cfg['P_min']) / cfg['beta']
    safe_print(f"  [2] {len(task_points)} task points, detection range={eff_range:.0f}km")
    safe_print(f"  [3] MOPSO: J={J}, N_bin={N_bin}, N_P={cfg['N_P']}, T_max={cfg['T_max']}...")

    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.0001
    )

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=cfg['N_P'], T_max=cfg['T_max'], c_1=2.0, c_2=2.0, p_c=0.9,
        archive_size=100, verbose=False,
        w_strategy='standard', p_m_base=0.01, select_gb='crowding'
    )

    t0 = time.time()
    archive, stats = mopso.optimize()
    elapsed = time.time() - t0

    safe_print(f"  [4] Done: {elapsed:.1f}s, {len(archive)} Pareto solutions")

    if len(archive) == 0:
        return {'name': cfg['name'], 'label': cfg['label'], 'error': 'no solutions'}

    # 后处理
    objectives = np.array([e['objectives'] for e in archive])
    ecr_vals, j_vals = [], []
    physics_list = []
    for entry in archive:
        cont = entry['continuous'].reshape(J, 2).flatten()
        bin_ = entry['binary']
        pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
        ecr = calculate_ecr(pos, task_points, radar_configs,
                            convex_polygons=polygons, binary_codes=bin_,
                            continuous_coords=cont.reshape(J, 2))
        jm = calculate_jamming_density(pos, task_points, radar_configs,
                                        convex_polygons=polygons, binary_codes=bin_,
                                        continuous_coords=cont.reshape(J, 2))
        ecr_vals.append(ecr)
        j_vals.append(jm)
        physics_list.append(pos)

    ecr_arr = np.array(ecr_vals)
    j_arr = np.array(j_vals)
    best_cov_idx, best_int_idx, knee_idx = get_extreme_points(objectives)

    # 超体积
    hv = 0.0
    si = np.argsort(objectives[:, 0])
    f1_s, f2_s = objectives[si, 0], objectives[si, 1]
    for k in range(1, len(f1_s)):
        hv += (f1_s[k] - f1_s[k-1]) * (1 - f2_s[k])
    hv += (1 - f1_s[-1]) * (1 - f2_s[-1])

    return {
        'name': cfg['name'], 'label': cfg['label'],
        'J': J, 'beta': cfg['beta'], 'eff_range': eff_range,
        'n_pareto': len(archive),
        'time': elapsed,
        'ecr_min': float(ecr_arr.min()), 'ecr_max': float(ecr_arr.max()),
        'j_min': float(j_arr.min()), 'j_max': float(j_arr.max()),
        'f1_min': float(objectives[:,0].min()), 'f1_max': float(objectives[:,0].max()),
        'f2_min': float(objectives[:,1].min()), 'f2_max': float(objectives[:,1].max()),
        'hypervolume': float(hv),
        'objectives': objectives,
        'ecr_arr': ecr_arr, 'j_arr': j_arr,
        'physics_list': physics_list,
        'best_cov_idx': best_cov_idx, 'best_int_idx': best_int_idx, 'knee_idx': knee_idx,
        'polygons': polygons, 'task_points': task_points,
        'N_bin': N_bin,
    }


def generate_comparison_figure(results):
    """生成三方案对比大图"""
    fig = plt.figure(figsize=(22, 18))

    colors_cfg = {'A_Fast': '#2E86AB', 'B_Standard': '#C73E1D', 'C_Challenging': '#6A994E'}
    markers_cfg = {'A_Fast': 'o', 'B_Standard': 's', 'C_Challenging': 'D'}

    # ---- 1. Pareto 前沿对比 (左上大图) ----
    ax1 = fig.add_subplot(2, 3, 1)
    for r in results:
        obj = r['objectives']
        ax1.scatter(obj[:, 0], obj[:, 1], c=colors_cfg[r['name']],
                    marker=markers_cfg[r['name']], s=70, alpha=0.8,
                    edgecolors='black', linewidth=0.5,
                    label=f"{r['label']} ({r['n_pareto']} sols)")
    ax1.set_xlabel('f1 = 1 - ECR', fontsize=11)
    ax1.set_ylabel('f2 = J_norm', fontsize=11)
    ax1.set_title('Pareto Front Comparison (Objective Space)', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # ---- 2. ECR vs J_min 物理空间 (中上) ----
    ax2 = fig.add_subplot(2, 3, 2)
    for r in results:
        ax2.scatter(r['ecr_arr'], r['j_arr'], c=colors_cfg[r['name']],
                    marker=markers_cfg[r['name']], s=70, alpha=0.7,
                    edgecolors='black', linewidth=0.5,
                    label=f"{r['label']}\nECR=[{r['ecr_min']:.3f},{r['ecr_max']:.3f}]")
    ax2.set_xlabel('ECR', fontsize=11)
    ax2.set_ylabel('J_min (W/m^2)', fontsize=11)
    ax2.set_title('ECR vs J_min (Physical Space)', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=8, loc='best')
    ax2.grid(True, alpha=0.3)

    # ---- 3. 指标对比条形图 (右上) ----
    ax3 = fig.add_subplot(2, 3, 3)
    metrics = ['Pareto\nSolutions', 'ECR\nRange', 'J_min\nRange(x1e-6)',
               'Hyper-\nvolume', 'Runtime\n(min)']
    x = np.arange(len(metrics))
    width = 0.22
    for i, r in enumerate(results):
        vals = [
            r['n_pareto'],
            r['ecr_max'] - r['ecr_min'],
            (r['j_max'] - r['j_min']) * 1e6,
            r['hypervolume'],
            r['time'] / 60,
        ]
        # 归一化到 [0,1]
        bars = ax3.bar(x + (i-1)*width, vals, width,
                       color=colors_cfg[r['name']], alpha=0.85,
                       edgecolor='black', linewidth=0.5,
                       label=r['label'])
        for bar, val in zip(bars, vals):
            if val > 0.01:
                ax3.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02*max(vals),
                         f'{val:.2f}'.rstrip('0').rstrip('.'),
                         ha='center', va='bottom', fontsize=7, rotation=90)
    ax3.set_xticks(x)
    ax3.set_xticklabels(metrics, fontsize=9)
    ax3.set_title('Performance Metrics Comparison', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=8)

    # ---- 4-6. 各配置的最佳覆盖部署图 (下排) ----
    for i_sub, r in enumerate(results):
        ax = fig.add_subplot(2, 3, 4 + i_sub)
        polygons = r['polygons']
        task_points = r['task_points']

        for poly in polygons:
            xp, yp = poly.exterior.xy
            ax.fill(xp, yp, alpha=0.12, color='lightblue', edgecolor='gray', linewidth=0.3)
        # 画孔洞
        for hole in HOLES:
            hx, hy = zip(*hole)
            ax.fill(hx, hy, alpha=0.3, color='white', edgecolor='darkgray', linewidth=0.5, linestyle='--')

        tx = [t.x for t in task_points[::3]]
        ty = [t.y for t in task_points[::3]]
        ax.scatter(tx, ty, c='lightgray', s=0.5, alpha=0.3)

        best_idx = r['best_cov_idx']
        pos = r['physics_list'][best_idx]
        ax.scatter(pos[:, 0], pos[:, 1], c='red', s=20, marker='^',
                   edgecolors='darkred', linewidth=0.3, zorder=5)

        ax.set_title(f"{r['label']}\nBest ECR={r['ecr_max']:.4f}, J_min={r['j_min']:.4e}",
                     fontsize=10, fontweight='bold')
        ax.set_xlim(-20, REGION_SIZE+20)
        ax.set_ylim(-20, REGION_SIZE+20)
        ax.set_xlabel('X (km)', fontsize=9)
        ax.set_ylabel('Y (km)', fontsize=9)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    plt.tight_layout(pad=2)
    fig_path = os.path.join(SAVE_DIR, 'batch_three_configs_comparison.png')
    plt.savefig(fig_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    safe_print(f"\n  Comparison figure saved: batch_three_configs_comparison.png")


# ============================================================================
# 主流程
# ============================================================================
safe_print("#" * 70)
safe_print("#  Batch Experiment: 3 Configurations on 1000km x 1000km")
safe_print("#" * 70)

all_results = []
for cfg in CONFIGS:
    result = run_config(cfg)
    all_results.append(result)

# ============================================================================
# 汇总报告
# ============================================================================
safe_print("\n\n" + "=" * 80)
safe_print("  FINAL SUMMARY")
safe_print("=" * 80)
safe_print(f"  {'Config':<30} {'Pareto':>7} {'ECR Range':>18} {'J_min Range':>20} {'Time':>8} {'HV':>7}")
safe_print(f"  {'':->30} {'':->7} {'':->18} {'':->20} {'':->8} {'':->7}")
for r in all_results:
    if 'error' in r:
        safe_print(f"  {r['label']:<30} {'ERROR':>7}")
    else:
        ecr_r = f"[{r['ecr_min']:.4f}, {r['ecr_max']:.4f}]"
        j_r = f"[{r['j_min']:.2e}, {r['j_max']:.2e}]"
        safe_print(f"  {r['label']:<30} {r['n_pareto']:>7} {ecr_r:>18} {j_r:>20} {r['time']:>7.0f}s {r['hypervolume']:>7.4f}")

safe_print("=" * 80)

# 分析
safe_print("\n  Analysis:")
for r in all_results:
    if 'error' not in r and r['n_pareto'] > 0:
        ecr_spread = r['ecr_max'] - r['ecr_min']
        j_spread = r['j_max'] - r['j_min']
        diversity = "GOOD" if ecr_spread > 0.05 and j_spread > 1e-7 else "FAIR" if ecr_spread > 0.02 else "NARROW"
        safe_print(f"    {r['label']}: Pareto diversity={diversity} "
                   f"(ECR spread={ecr_spread:.4f}, J spread={j_spread:.2e})")

# ============================================================================
# 生成对比图
# ============================================================================
valid_results = [r for r in all_results if 'error' not in r and r['n_pareto'] > 0]
if valid_results:
    generate_comparison_figure(valid_results)

safe_print("\n  All experiments complete!")
