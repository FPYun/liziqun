"""
200km 区域 G2G 干扰模型三配置对比实验

核心修正：is_air=False → 干扰使用 alpha=4 (1/d^4) 衰减
         → 探测用指数衰减，干扰用快速幂律衰减 → 产生真正的 Pareto 冲突
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time, sys, os

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
from shapely.geometry import Polygon as SPolygon

SAVE_DIR = os.path.join(PROJECT_ROOT, 'figures')
os.makedirs(SAVE_DIR, exist_ok=True)

REGION_SIZE = 200
P0, P_MIN = 0.95, 0.8
GRID = 15

CONFIGS = [
    {'name': 'A_Fast',    'label': 'A: 5 radars, beta=0.02',  'J': 5,  'beta': 0.02, 'N_P': 50, 'T_max': 60},
    {'name': 'B_Paper',   'label': 'B: 8 radars, beta=0.03',  'J': 8,  'beta': 0.03, 'N_P': 50, 'T_max': 80},
    {'name': 'C_Hard',    'label': 'C: 10 radars, beta=0.03', 'J': 10, 'beta': 0.03, 'N_P': 50, 'T_max': 80},
]


def safe_print(*args):
    try:
        print(*args)
    except UnicodeEncodeError:
        print(*(str(a).encode('ascii', errors='replace').decode('ascii') for a in args))


def run_config(cfg):
    safe_print(f"\n{'='*60}")
    safe_print(f"  {cfg['label']}  |  G2G jamming (alpha=4)")
    safe_print(f"{'='*60}")

    region = SPolygon([(0, 0), (REGION_SIZE, 0), (REGION_SIZE, REGION_SIZE), (0, REGION_SIZE)])
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    J = cfg['J']
    rng = np.log(P0 / P_MIN) / cfg['beta']
    safe_print(f"  Detection range: {rng:.0f}km, J={J}, N_P={cfg['N_P']}, T_max={cfg['T_max']}")

    cfgs = [RadarConfig(P0=P0, P_min=P_MIN, beta=cfg['beta'], is_air=False) for _ in range(J)]
    task_points = generate_uniform_task_points(region, grid_size=GRID)

    evaluate_func = create_normalized_evaluate_function(
        task_points, cfgs, polygons, J, N_bin, J_max_ref=0.001
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

    if len(archive) == 0:
        return {'name': cfg['name'], 'label': cfg['label'], 'error': 'no solutions'}

    objectives = np.array([e['objectives'] for e in archive])
    ecrs, jmins = [], []
    physics_list = []
    for entry in archive:
        cont = entry['continuous'].reshape(J, 2).flatten()
        bin_ = entry['binary']
        pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
        ecr = calculate_ecr(pos, task_points, cfgs, convex_polygons=polygons,
                            binary_codes=bin_, continuous_coords=cont.reshape(J, 2))
        jm = calculate_jamming_density(pos, task_points, cfgs, convex_polygons=polygons,
                                        binary_codes=bin_, continuous_coords=cont.reshape(J, 2))
        ecrs.append(ecr)
        jmins.append(jm)
        physics_list.append(pos)

    ecr_arr = np.array(ecrs)
    jm_arr = np.array(jmins)
    best_cov, best_jam, knee = get_extreme_points(objectives)
    corr = np.corrcoef(ecr_arr, jm_arr)[0, 1] if len(archive) > 2 else 0

    hv = 0.0
    si = np.argsort(objectives[:, 0])
    f1_s, f2_s = objectives[si, 0], objectives[si, 1]
    for k in range(1, len(f1_s)):
        hv += (f1_s[k] - f1_s[k-1]) * (1 - f2_s[k])
    hv += (1 - f1_s[-1]) * (1 - f2_s[-1])

    safe_print(f"  Done: {elapsed:.0f}s, {len(archive)} solutions")
    safe_print(f"  ECR: [{ecr_arr.min():.4f}, {ecr_arr.max():.4f}]")
    safe_print(f"  J_min: [{jm_arr.min():.2e}, {jm_arr.max():.2e}]")
    safe_print(f"  ECR vs J_min corr: {corr:+.3f}")
    safe_print(f"  Best ECR={ecr_arr[best_cov]:.4f} (J_min={jm_arr[best_cov]:.2e})")
    safe_print(f"  Best J_min={jm_arr[best_jam]:.2e} (ECR={ecr_arr[best_jam]:.4f})")

    return {
        'name': cfg['name'], 'label': cfg['label'],
        'J': J, 'beta': cfg['beta'], 'range': rng,
        'n_pareto': len(archive), 'time': elapsed,
        'ecr_min': float(ecr_arr.min()), 'ecr_max': float(ecr_arr.max()),
        'jm_min': float(jm_arr.min()), 'jm_max': float(jm_arr.max()),
        'hypervolume': float(hv), 'correlation': float(corr),
        'objectives': objectives, 'ecr_arr': ecr_arr, 'jm_arr': jm_arr,
        'physics_list': physics_list,
        'best_cov_idx': best_cov, 'best_jam_idx': best_jam, 'knee_idx': knee,
        'polygons': polygons, 'task_points': task_points, 'N_bin': N_bin,
    }


def generate_figure(results):
    colors = {'A_Fast': '#2E86AB', 'B_Paper': '#C73E1D', 'C_Hard': '#6A994E'}
    markers = {'A_Fast': 'o', 'B_Paper': 's', 'C_Hard': 'D'}

    fig = plt.figure(figsize=(20, 12))

    # 1. Pareto 前沿 (f1=1-ECR, f2=J_norm)
    ax1 = fig.add_subplot(2, 3, 1)
    for r in results:
        obj = r['objectives']
        ax1.scatter(obj[:, 0], obj[:, 1], c=colors[r['name']], marker=markers[r['name']],
                    s=50, alpha=0.8, edgecolors='black', linewidth=0.3,
                    label=f"{r['label']} ({r['n_pareto']} sols)")
    ax1.set_xlabel('f1 = 1 - ECR', fontsize=11)
    ax1.set_ylabel('f2 = J_norm', fontsize=11)
    ax1.set_title('Pareto Front (Objective Space)', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # 2. ECR vs J_min 物理空间
    ax2 = fig.add_subplot(2, 3, 2)
    for r in results:
        ax2.scatter(r['ecr_arr'], r['jm_arr'], c=colors[r['name']], marker=markers[r['name']],
                    s=50, alpha=0.7, edgecolors='black', linewidth=0.3,
                    label=f"{r['label']}\nr={r['correlation']:+.3f}")
    ax2.set_xlabel('ECR', fontsize=11)
    ax2.set_ylabel('J_min (W/m^2)', fontsize=11)
    ax2.set_title('ECR vs J_min (Physical Space)', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3. 指标对比
    ax3 = fig.add_subplot(2, 3, 3)
    metrics = ['Solutions', 'ECR Range', 'J_min Range\n(x1e-10)', 'Hypervolume', 'Time (s)']
    x = np.arange(len(metrics))
    width = 0.22
    for i, r in enumerate(results):
        vals = [r['n_pareto'], r['ecr_max'] - r['ecr_min'],
                (r['jm_max'] - r['jm_min']) * 1e10, r['hypervolume'], r['time']]
        bars = ax3.bar(x + (i-1)*width, vals, width, color=colors[r['name']], alpha=0.85,
                       edgecolor='black', linewidth=0.5, label=r['label'])
        for bar, val in zip(bars, vals):
            if val > 0.001:
                ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                         f'{val:.2f}'.rstrip('0').rstrip('.'),
                         ha='center', va='bottom', fontsize=7, rotation=90)
    ax3.set_xticks(x)
    ax3.set_xticklabels(metrics, fontsize=9)
    ax3.set_title('Performance Metrics', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=8)

    # 4-6. 各配置最佳覆盖部署图
    for i_sub, r in enumerate(results):
        ax = fig.add_subplot(2, 3, 4 + i_sub)
        for poly in r['polygons']:
            xp, yp = poly.exterior.xy
            ax.fill(xp, yp, alpha=0.12, color='lightblue', edgecolor='gray', linewidth=0.3)
        tx = [t.x for t in r['task_points']]
        ty = [t.y for t in r['task_points']]
        ax.scatter(tx, ty, c='lightgray', s=3, alpha=0.3)

        best_idx = r['best_cov_idx']
        pos = r['physics_list'][best_idx]
        ax.scatter(pos[:, 0], pos[:, 1], c='red', s=60, marker='^',
                   edgecolors='darkred', linewidth=1, zorder=5)
        ax.set_title(f"{r['label']}\nBest ECR={r['ecr_max']:.4f}, J_min={r['jm_min']:.2e}",
                     fontsize=10, fontweight='bold')
        ax.set_xlim(-5, REGION_SIZE + 5)
        ax.set_ylim(-5, REGION_SIZE + 5)
        ax.set_xlabel('X (km)', fontsize=9)
        ax.set_ylabel('Y (km)', fontsize=9)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    plt.tight_layout(pad=2)
    fig_path = os.path.join(SAVE_DIR, '200km_g2g_comparison.png')
    plt.savefig(fig_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    safe_print(f"\n  Figure saved: 200km_g2g_comparison.png")


# ============================================================================
safe_print("=" * 70)
safe_print("  200km G2G Jamming: 3 Configurations (alpha=4, 1/d^4 decay)")
safe_print("=" * 70)

all_results = []
for cfg in CONFIGS:
    result = run_config(cfg)
    all_results.append(result)

# Summary
safe_print("\n\n" + "=" * 70)
safe_print("  FINAL SUMMARY")
safe_print("=" * 70)
safe_print(f"  {'Config':<30} {'Sol':>4} {'ECR Range':>16} {'J_min Range':>22} {'Corr':>7} {'Time':>6}")
safe_print(f"  {'':->30} {'':->4} {'':->16} {'':->22} {'':->7} {'':->6}")
for r in all_results:
    if 'error' in r:
        safe_print(f"  {r['label']:<30} ERROR")
    else:
        ecr_r = f"[{r['ecr_min']:.4f},{r['ecr_max']:.4f}]"
        j_r = f"[{r['jm_min']:.2e},{r['jm_max']:.2e}]"
        safe_print(f"  {r['label']:<30} {r['n_pareto']:>4} {ecr_r:>16} {j_r:>22} {r['correlation']:>+7.3f} {r['time']:>5.0f}s")
safe_print("=" * 70)

generate_figure(all_results)
safe_print("\n  Done!")
