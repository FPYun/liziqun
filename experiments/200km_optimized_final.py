"""
200km 优化后最终实验：fixed w=0.4 + Jref=1e-8

对比优化前 (standard w, Jref=0.001) vs 优化后
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
from src.evaluation import (RadarConfig, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density, decode_particle,
    create_normalized_evaluate_function)
from src.mopso import MOPSO_DT
from src.benchmarks import get_extreme_points
from shapely.geometry import Polygon as SPolygon

SAVE_DIR = os.path.join(PROJECT_ROOT, 'figures')
os.makedirs(SAVE_DIR, exist_ok=True)

REGION_SIZE = 200
P0, P_MIN = 0.95, 0.8
GRID = 15

CONFIGS = [
    {'name': 'A', 'label': 'A: 5 radars, beta=0.02',  'J': 5,  'beta': 0.02},
    {'name': 'B', 'label': 'B: 8 radars, beta=0.03',  'J': 8,  'beta': 0.03},
    {'name': 'C', 'label': 'C: 10 radars, beta=0.03', 'J': 10, 'beta': 0.03},
]

# 优化前后设置
SETTINGS = [
    {'tag': 'BEFORE', 'w': 'standard', 'jref': 0.001, 'eps': 0.0,  'T_max': 80},
    {'tag': 'AFTER',  'w': 'fixed',    'jref': 1e-8,   'eps': 5e-5, 'T_max': 80},
]


def safe_print(*args, **kwargs):
    try: print(*args, **kwargs)
    except UnicodeEncodeError: print(*(str(a).encode('ascii',errors='replace').decode('ascii') for a in args), **kwargs)


def run_one(cfg, setting):
    region = SPolygon([(0,0),(REGION_SIZE,0),(REGION_SIZE,REGION_SIZE),(0,REGION_SIZE)])
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    J = cfg['J']
    rng = np.log(P0 / P_MIN) / cfg['beta']
    cfgs = [RadarConfig(P0=P0, P_min=P_MIN, beta=cfg['beta'], is_air=False) for _ in range(J)]
    tp = generate_uniform_task_points(region, grid_size=GRID)

    ev = create_normalized_evaluate_function(tp, cfgs, polygons, J, N_bin, J_max_ref=setting['jref'])

    mopso = MOPSO_DT(J=J, N_bin=N_bin, evaluate_func=ev,
        N_P=50, T_max=setting['T_max'], c_1=2.0, c_2=2.0, p_c=0.9,
        archive_size=100, verbose=False,
        w_strategy=setting['w'], p_m_base=0.01, select_gb='crowding',
        epsilon=setting['eps'])

    t0 = time.time()
    archive, stats = mopso.optimize()
    elapsed = time.time() - t0

    if len(archive) < 3:
        return None

    objectives = np.array([e['objectives'] for e in archive])
    ecrs, jms, physics = [], [], []
    for entry in archive:
        cont = entry['continuous'].reshape(J, 2).flatten()
        bin_ = entry['binary']
        pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
        ecr = calculate_ecr(pos, tp, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(J,2))
        jm = calculate_jamming_density(pos, tp, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(J,2))
        ecrs.append(ecr); jms.append(jm); physics.append(pos)

    ecr_arr, jm_arr = np.array(ecrs), np.array(jms)
    corr = np.corrcoef(ecr_arr, jm_arr)[0, 1]
    best_cov, best_jam, knee = get_extreme_points(objectives)

    # Hypervolume
    hv = 0.0
    si = np.argsort(objectives[:, 0])
    f1_s, f2_s = objectives[si, 0], objectives[si, 1]
    for k in range(1, len(f1_s)):
        hv += (f1_s[k] - f1_s[k-1]) * (1 - f2_s[k])
    hv += (1 - f1_s[-1]) * (1 - f2_s[-1])

    return {
        'name': cfg['name'], 'label': cfg['label'], 'tag': setting['tag'],
        'J': J, 'beta': cfg['beta'], 'range': rng,
        'n_pareto': len(archive), 'time': elapsed,
        'ecr_min': float(ecr_arr.min()), 'ecr_max': float(ecr_arr.max()),
        'jm_min': float(jm_arr.min()), 'jm_max': float(jm_arr.max()),
        'correlation': float(corr), 'hypervolume': float(hv),
        'objectives': objectives, 'ecr_arr': ecr_arr, 'jm_arr': jm_arr,
        'physics_list': physics,
        'best_cov_idx': best_cov, 'best_jam_idx': best_jam, 'knee_idx': knee,
        'polygons': polygons, 'task_points': tp, 'N_bin': N_bin,
    }


# ============================================================================
safe_print("=" * 70)
safe_print("  Optimized Experiment: 200km G2G Jamming")
safe_print(f"  w=fixed(0.4), Jref=1e-8, eps=5e-5, T_max=80")
safe_print("=" * 70)

all_results = []
for cfg in CONFIGS:
    for st in SETTINGS:
        safe_print(f"\n  [{st['tag']}] {cfg['label']} ...", end=' ', flush=True)
        r = run_one(cfg, st)
        if r:
            safe_print(f"{r['time']:.0f}s, {r['n_pareto']} sols, "
                       f"ECR[{r['ecr_min']:.4f},{r['ecr_max']:.4f}], |r|={abs(r['correlation']):.3f}")
            all_results.append(r)
        else:
            safe_print("FAILED")

# ============================================================================
# Summary table
# ============================================================================
safe_print("\n\n" + "=" * 80)
safe_print("  RESULTS SUMMARY")
safe_print("=" * 80)
safe_print(f"  {'Config':<28} {'Ver':>6} {'Sol':>4} {'ECR Range':>16} {'|r|':>7} {'Time':>5}")
safe_print(f"  {'':->28} {'':->6} {'':->4} {'':->16} {'':->7} {'':->5}")
before_map = {}
after_map = {}
for r in all_results:
    k = r['name']
    ecr_r = f"[{r['ecr_min']:.4f},{r['ecr_max']:.4f}]"
    safe_print(f"  {r['label']:<28} {r['tag']:>6} {r['n_pareto']:>4} {ecr_r:>16} {abs(r['correlation']):>7.3f} {r['time']:>4.0f}s")
    if r['tag'] == 'BEFORE': before_map[k] = r
    else: after_map[k] = r

safe_print("=" * 80)
safe_print("\n  Improvement (|r|):")
for k in ['A', 'B', 'C']:
    if k in before_map and k in after_map:
        delta = abs(after_map[k]['correlation']) - abs(before_map[k]['correlation'])
        pct = delta / abs(before_map[k]['correlation']) * 100
        safe_print(f"    Config {k}: {abs(before_map[k]['correlation']):.3f} -> {abs(after_map[k]['correlation']):.3f}  ({pct:+.0f}%)")

# ============================================================================
# Visualization: before vs after Pareto fronts side by side
# ============================================================================
safe_print("\n  Generating figures...")

fig = plt.figure(figsize=(20, 12))
colors_cfg = {'A': '#2E86AB', 'B': '#C73E1D', 'C': '#6A994E'}

# Row 1: BEFORE Pareto fronts
for i, r in enumerate([x for x in all_results if x['tag'] == 'BEFORE']):
    ax = fig.add_subplot(2, 3, 1 + i)
    obj = r['objectives']
    ax.scatter(obj[:, 0], obj[:, 1], c=colors_cfg[r['name']], s=40, alpha=0.8,
               edgecolors='black', linewidth=0.3)
    ax.set_xlabel('1 - ECR', fontsize=10)
    ax.set_ylabel('J_norm', fontsize=10)
    ax.set_title(f"BEFORE: {r['label']}\n|r|={abs(r['correlation']):.3f}, {r['n_pareto']} sols",
                 fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)

# Row 2: AFTER Pareto fronts
for i, r in enumerate([x for x in all_results if x['tag'] == 'AFTER']):
    ax = fig.add_subplot(2, 3, 4 + i)
    obj = r['objectives']
    ax.scatter(obj[:, 0], obj[:, 1], c=colors_cfg[r['name']], s=40, alpha=0.8,
               edgecolors='black', linewidth=0.3)
    ax.set_xlabel('1 - ECR', fontsize=10)
    ax.set_ylabel('J_norm', fontsize=10)
    ax.set_title(f"AFTER: {r['label']}\n|r|={abs(r['correlation']):.3f}, {r['n_pareto']} sols",
                 fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)

plt.tight_layout(pad=2)
fig_path = os.path.join(SAVE_DIR, '200km_optimized_comparison.png')
plt.savefig(fig_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

# ============================================================================
# Deployment maps for AFTER configs
# ============================================================================
after_results = [r for r in all_results if r['tag'] == 'AFTER']
fig2 = plt.figure(figsize=(18, 5))
for i_sub, r in enumerate(after_results):
    ax = fig2.add_subplot(1, 3, 1 + i_sub)
    for poly in r['polygons']:
        xp, yp = poly.exterior.xy
        ax.fill(xp, yp, alpha=0.12, color='lightblue', edgecolor='gray', linewidth=0.3)
    tx = [t.x for t in r['task_points']]
    ty = [t.y for t in r['task_points']]
    ax.scatter(tx, ty, c='lightgray', s=3, alpha=0.3)

    best_idx = r['best_cov_idx']
    pos = r['physics_list'][best_idx]
    ax.scatter(pos[:, 0], pos[:, 1], c='red', s=80, marker='^',
               edgecolors='darkred', linewidth=1, zorder=5)
    for jj, (px, py) in enumerate(pos):
        ax.annotate(str(jj+1), (px, py), fontsize=6, ha='center', va='bottom')
    ax.set_title(f"{r['label']}\nBest ECR={r['ecr_max']:.4f}, |r|={abs(r['correlation']):.3f}",
                 fontsize=11, fontweight='bold')
    ax.set_xlim(-5, REGION_SIZE+5); ax.set_ylim(-5, REGION_SIZE+5)
    ax.set_aspect('equal'); ax.grid(True, alpha=0.3)

plt.tight_layout(pad=2)
fig_path2 = os.path.join(SAVE_DIR, '200km_optimized_deployments.png')
plt.savefig(fig_path2, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

safe_print(f"  Figures saved: 200km_optimized_comparison.png, 200km_optimized_deployments.png")
safe_print("\n  Done!")
