"""
优化前后 A/B 对比：fixed w=0.4 + epsilon-dominance
"""
import numpy as np, time, sys
sys.path.insert(0, '.')
from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (RadarConfig, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density, decode_particle,
    create_normalized_evaluate_function)
from src.mopso import MOPSO_DT
from src.benchmarks import get_extreme_points
from shapely.geometry import Polygon as SPolygon

REGION_SIZE = 200; GRID = 15; P0=0.95; P_MIN=0.8

CONFIGS = [
    # Before: standard strategy, no epsilon
    {'label': 'BEFORE: standard w, eps=0',     'J': 8, 'beta': 0.03, 'N_P': 50, 'T_max': 80,  'w': 'standard', 'eps': 0.0},
    # After: fixed w=0.4, epsilon=1e-4, more iterations
    {'label': 'AFTER:  fixed w=0.4, eps=1e-4', 'J': 8, 'beta': 0.03, 'N_P': 50, 'T_max': 80,  'w': 'fixed',    'eps': 1e-4},
    {'label': 'AFTER+: fixed w, eps=1e-4, T120','J': 8, 'beta': 0.03, 'N_P': 50, 'T_max': 120, 'w': 'fixed',    'eps': 1e-4},
    # Also test paper-aligned config: w='fixed', eps=1e-3 (coarser)
    {'label': 'AFTER++:fixed w, eps=1e-3, T120','J': 8, 'beta': 0.03, 'N_P': 50, 'T_max': 120, 'w': 'fixed',    'eps': 1e-3},
]


def run(cfg):
    print(f"\n  {cfg['label']} ...", end=' ', flush=True)
    region = SPolygon([(0,0),(REGION_SIZE,0),(REGION_SIZE,REGION_SIZE),(0,REGION_SIZE)])
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    cfgs = [RadarConfig(P0=P0, P_min=P_MIN, beta=cfg['beta'], is_air=False) for _ in range(cfg['J'])]
    tp = generate_uniform_task_points(region, grid_size=GRID)
    ev = create_normalized_evaluate_function(tp, cfgs, polygons, cfg['J'], N_bin, J_max_ref=0.001)

    mopso = MOPSO_DT(J=cfg['J'], N_bin=N_bin, evaluate_func=ev,
        N_P=cfg['N_P'], T_max=cfg['T_max'], archive_size=100, verbose=False,
        w_strategy=cfg['w'], p_m_base=0.01, select_gb='crowding',
        epsilon=cfg['eps'])

    t0=time.time()
    archive, _ = mopso.optimize()
    elapsed=time.time()-t0

    if len(archive) < 3: return None

    objectives = np.array([e['objectives'] for e in archive])
    ecrs, jms = [], []
    for entry in archive:
        cont = entry['continuous'].reshape(cfg['J'], 2).flatten()
        bin_ = entry['binary']
        pos = np.array(decode_particle(cont, bin_, cfg['J'], N_bin, polygons))
        ecr = calculate_ecr(pos, tp, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(cfg['J'],2))
        jm = calculate_jamming_density(pos, tp, cfgs, convex_polygons=polygons, binary_codes=bin_, continuous_coords=cont.reshape(cfg['J'],2))
        ecrs.append(ecr); jms.append(jm)

    ecr_arr=np.array(ecrs); jm_arr=np.array(jms)
    corr = np.corrcoef(ecr_arr, jm_arr)[0,1]
    ecr_spread = ecr_arr.max()-ecr_arr.min()
    jm_spread = jm_arr.max()-jm_arr.min()

    print(f"{elapsed:.0f}s, {len(archive)} sols, ECR[{ecr_arr.min():.4f},{ecr_arr.max():.4f}], corr={corr:+.3f}")
    return elapsed, len(archive), float(ecr_spread), abs(corr), float(jm_spread)


print("=" * 70)
print("  A/B Comparison: Before vs After Optimization")
print(f"  {REGION_SIZE}km, J=8, beta=0.03, G2G jamming")
print("=" * 70)

results = []
for cfg in CONFIGS:
    r = run(cfg)
    if r: results.append((cfg['label'], r))

print("\n" + "=" * 70)
print(f"  {'Config':<35} {'Time':>5} {'Sols':>5} {'ECR spr':>8} {'|r|':>6}")
print(f"  {'':->35} {'':->5} {'':->5} {'':->8} {'':->6}")
for label, (t, n, es, corr, js) in results:
    print(f"  {label:<35} {t:>4.0f}s {n:>5} {es:>8.4f} {corr:>6.3f}")
print("=" * 70)

if len(results) >= 2:
    _, r_before = results[0]
    for label, r_after in results[1:]:
        imp = (r_after[3] - r_before[3]) / r_before[3] * 100
        print(f"  {label.split(':')[0]} vs BEFORE: |r| improvement = {imp:+.0f}%")
