"""
Core Ablation Studies for MOPSO-DT Paper
=========================================
Tests: propagation | transform | normalization | region | radar_count

Usage:
  python experiments/ablation_core.py --ablation propagation
  python experiments/ablation_core.py --ablation transform
  python experiments/ablation_core.py --ablation normalization
  python experiments/ablation_core.py --ablation region
  python experiments/ablation_core.py --ablation radar_count
  python experiments/ablation_core.py --ablation all
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os, time, argparse

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, create_normalized_evaluate_function,
    create_evaluate_function
)
from src.mopso import MOPSO_DT
from src.benchmarks import find_knee_point
from shapely.geometry import Polygon as ShapelyPolygon


def run_ablation(config, label):
    """Generic ablation runner. Returns (solutions, objectives, ecr_list, jmin_list)."""
    region = config['region']
    radar_configs = config['radar_configs']
    task_points = config['task_points']
    J = config['J']
    T_max = config.get('T_max', 80)
    N_P = config.get('N_P', 50)
    evaluate_func = config['evaluate_func']

    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=N_P, T_max=T_max, c_1=2.0, c_2=2.0,
        p_m_base=0.01, archive_size=100, verbose=False,
        w_strategy='standard', select_gb='crowding'
    )

    t0 = time.time()
    pareto_archive, _ = mopso.optimize()
    elapsed = time.time() - t0

    solutions, objectives, ecr_list, jmin_list = [], [], [], []
    for entry in pareto_archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        solutions.append(sol)
        objectives.append(entry['objectives'])

        continuous = sol[:, :2].flatten()
        binary = sol[:, 2:2+N_bin]
        positions = decode_particle(continuous, binary, J, N_bin, polygons)
        pa = np.array(positions)

        ecr = calculate_ecr(pa, task_points, radar_configs,
                           convex_polygons=polygons, binary_codes=binary,
                           continuous_coords=continuous.reshape(J, 2))
        jmin = calculate_jamming_density(pa, task_points, radar_configs,
                                         convex_polygons=polygons, binary_codes=binary,
                                         continuous_coords=continuous.reshape(J, 2))
        ecr_list.append(ecr)
        jmin_list.append(jmin)

    obj = np.array(objectives)
    ecr_a = np.array(ecr_list)
    jmin_a = np.array(jmin_list)
    corr = np.corrcoef(ecr_a, jmin_a)[0, 1] if len(ecr_a) > 2 else 0

    print(f"  [{label}] Pareto: {len(solutions)} | ECR: [{ecr_a.min():.4f}, {ecr_a.max():.4f}] | "
          f"J_min: [{jmin_a.min():.6f}, {jmin_a.max():.6f}] | r={corr:.4f} | {elapsed:.1f}s")
    return solutions, obj, ecr_a, jmin_a, elapsed, corr


# ===== A1: UNIFORM vs HETEROGENEOUS PROPAGATION =====
def ablation_propagation():
    print("\n" + "="*60)
    print("A1: 传播模型消融 — 统一α=3.0 vs 异构α=2.0/4.0")
    print("="*60)

    region = ShapelyPolygon([(0,0),(200,0),(200,200),(0,200)])
    task_points = generate_uniform_task_points(region, grid_size=15)
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, n_bits = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    # Baseline: heterogeneous
    hetero_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03,
                                   alpha_air=2.0, alpha_ground=4.0,
                                   jammer_P_t=150.0, jammer_G_t_dB=30.0)
                      for _ in range(8)]
    J_ref = 0.005
    hetero_eval = create_normalized_evaluate_function(
        task_points, hetero_configs, polygons, 8, N_bin, J_max_ref=J_ref)

    # Ablation: uniform α=3.0
    uniform_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03,
                                    alpha_air=3.0, alpha_ground=3.0,
                                    jammer_P_t=150.0, jammer_G_t_dB=30.0)
                       for _ in range(8)]
    uniform_eval = create_normalized_evaluate_function(
        task_points, uniform_configs, polygons, 8, N_bin, J_max_ref=J_ref)

    cfg = {'region': region, 'task_points': task_points, 'J': 8}

    _, _, ecr_h, j_h, _, r_h = run_ablation(
        {**cfg, 'radar_configs': hetero_configs, 'evaluate_func': hetero_eval},
        "Heterogeneous")

    _, _, ecr_u, j_u, _, r_u = run_ablation(
        {**cfg, 'radar_configs': uniform_configs, 'evaluate_func': uniform_eval},
        "Uniform α=3.0")

    print(f"\n  Summary: Hetero ECR=[{ecr_h.min():.3f},{ecr_h.max():.3f}] r={r_h:.3f}")
    print(f"           Uniform ECR=[{ecr_u.min():.3f},{ecr_u.max():.3f}] r={r_u:.3f}")
    print(f"  Conclusion: {'异构模型产生显著不同的Pareto前沿' if abs(r_h-r_u)>0.05 else '传播模型选择对Pareto前沿影响有限'}")

    return {'hetero_ecr': ecr_h, 'hetero_jmin': j_h, 'hetero_r': r_h,
            'uniform_ecr': ecr_u, 'uniform_jmin': j_u, 'uniform_r': r_u}


# ===== A2: WITH vs WITHOUT COORDINATE TRANSFORM =====
def ablation_transform():
    print("\n" + "="*60)
    print("A2: 坐标变换消融 — 归一化空间 vs 直接物理空间")
    print("="*60)

    region = ShapelyPolygon([(0,0),(200,0),(200,200),(0,200)])
    task_points = generate_uniform_task_points(region, grid_size=15)
    radar_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03)
                     for _ in range(8)]
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)

    # Direct physical-space evaluate function
    def direct_evaluate_func(Phi):
        """Optimize directly in physical coordinates (no coordinate transform)."""
        J, N_bin = 8, 1
        continuous = Phi[:, :2].flatten()
        binary = Phi[:, 2:2+N_bin]
        # Use polygon centroid + scale continuous coords to physical space
        positions = []
        bounds = region.bounds  # (minx, miny, maxx, maxy)
        for j in range(J):
            x = bounds[0] + continuous[2*j] * (bounds[2] - bounds[0])
            y = bounds[1] + continuous[2*j+1] * (bounds[3] - bounds[1])
            # Clamp to region
            from shapely.geometry import Point
            pt = Point(x, y)
            if not region.contains(pt):
                nearest = region.exterior.interpolate(region.exterior.project(pt))
                x, y = nearest.x, nearest.y
            positions.append((x, y))
        pa = np.array(positions)
        ecr = calculate_ecr(pa, task_points, radar_configs)
        jmin = calculate_jamming_density(pa, task_points, radar_configs)
        return np.array([1 - ecr, 0.005 / (jmin + 0.005 + 1e-10)])

    # Normalized space (with coordinate transform) — baseline
    norm_eval = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, 8, 1, J_max_ref=0.005)

    cfg = {'region': region, 'task_points': task_points, 'J': 8,
           'radar_configs': radar_configs}

    _, _, ecr_n, j_n, _, r_n = run_ablation(
        {**cfg, 'evaluate_func': norm_eval}, "With Transform")

    _, _, ecr_d, j_d, _, r_d = run_ablation(
        {**cfg, 'evaluate_func': direct_evaluate_func}, "Direct Physical")

    print(f"\n  Summary: Transform  ECR=[{ecr_n.min():.3f},{ecr_n.max():.3f}] r={r_n:.3f}")
    print(f"           Direct     ECR=[{ecr_d.min():.3f},{ecr_d.max():.3f}] r={r_d:.3f}")
    print(f"  Conclusion: {'坐标变换显著改善边界覆盖' if ecr_n.max()-ecr_d.max()>0.02 else '坐标变换效果不明显'}")

    return {'transform_ecr': ecr_n, 'transform_r': r_n,
            'direct_ecr': ecr_d, 'direct_r': r_d}


# ===== A3: NORMALIZED vs RAW OBJECTIVES =====
def ablation_normalization():
    print("\n" + "="*60)
    print("A3: 目标函数消融 — 归一化f2 vs 原始1/J_min")
    print("="*60)

    region = ShapelyPolygon([(0,0),(200,0),(200,200),(0,200)])
    task_points = generate_uniform_task_points(region, grid_size=15)
    radar_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03)
                     for _ in range(8)]
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)

    norm_eval = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, 8, 1, J_max_ref=0.005)
    raw_eval = create_evaluate_function(task_points, radar_configs, polygons, 8, 1)

    cfg = {'region': region, 'task_points': task_points, 'J': 8,
           'radar_configs': radar_configs}

    _, obj_n, ecr_n, j_n, _, r_n = run_ablation(
        {**cfg, 'evaluate_func': norm_eval}, "Normalized")

    _, obj_r, ecr_r, j_r, _, r_r = run_ablation(
        {**cfg, 'evaluate_func': raw_eval}, "Raw 1/J_min")

    print(f"\n  Summary: Norm ECR=[{ecr_n.min():.3f},{ecr_n.max():.3f}] sols={len(ecr_n)} r={r_n:.3f}")
    print(f"           Raw  ECR=[{ecr_r.min():.3f},{ecr_r.max():.3f}] sols={len(ecr_r)} r={r_r:.3f}")
    print(f"  Conclusion: {'归一化显著提升Pareto多样性' if len(ecr_n)>len(ecr_r)*1.5 else '归一化对Pareto多样性影响有限'}")

    return {'norm_ecr': ecr_n, 'norm_nsols': len(ecr_n), 'norm_r': r_n,
            'raw_ecr': ecr_r, 'raw_nsols': len(ecr_r), 'raw_r': r_r,
            'norm_obj': obj_n, 'raw_obj': obj_r}


# ===== A4: REGION SHAPE COMPLEXITY =====
def ablation_region():
    print("\n" + "="*60)
    print("A4: 区域复杂度消融 — 矩形 vs L形 vs 带空洞")
    print("="*60)

    regions = {
        'Rectangle': ShapelyPolygon([(0,0),(200,0),(200,200),(0,200)]),
        'L-Shape': ShapelyPolygon([(0,0),(200,0),(200,80),(80,80),(80,200),(0,200)]),
        'With Hole': ShapelyPolygon(
            [(0,0),(200,0),(200,200),(0,200)],
            holes=[[(60,60),(140,60),(140,140),(60,140)]])
    }

    results = {}
    for name, region in regions.items():
        decomposer = DeploymentRegionDecomposer(verbose=False)
        polygons, _, _ = decomposer.decompose(region)
        n_polys = len(polygons)
        task_points = generate_uniform_task_points(region, grid_size=15)
        radar_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03)
                         for _ in range(8)]
        J_max_ref = 0.005

        N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
        evaluate_func = create_normalized_evaluate_function(
            task_points, radar_configs, polygons, 8, N_bin, J_max_ref=J_max_ref)

        cfg = {'region': region, 'task_points': task_points, 'J': 8,
               'radar_configs': radar_configs, 'evaluate_func': evaluate_func}
        _, obj, ecr, jmin, elapsed, corr = run_ablation(cfg, f"{name} ({n_polys} polys)")

        results[name] = {'n_polygons': n_polys, 'ecr': ecr, 'jmin': jmin,
                         'n_sols': len(ecr), 'corr': corr, 'time': elapsed}

    print(f"\n  Region    Polys  Sols  ECR Range         r")
    for name, r in results.items():
        print(f"  {name:<10} {r['n_polygons']:<6} {r['n_sols']:<5} "
              f"[{r['ecr'].min():.3f},{r['ecr'].max():.3f}]   {r['corr']:.3f}")

    return results


# ===== A5: RADAR COUNT SENSITIVITY =====
def ablation_radar_count():
    print("\n" + "="*60)
    print("A5: 雷达数量灵敏度 — J ∈ {4, 6, 8, 10, 12}")
    print("="*60)

    region = ShapelyPolygon([(0,0),(200,0),(200,200),(0,200)])
    task_points = generate_uniform_task_points(region, grid_size=15)
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, _, _ = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    results = {}
    for J in [4, 6, 8, 10, 12]:
        radar_configs = [RadarConfig(P0=0.9, P_min=0.8, beta=0.03)
                         for _ in range(J)]
        evaluate_func = create_normalized_evaluate_function(
            task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.005)

        cfg = {'region': region, 'task_points': task_points, 'J': J,
               'radar_configs': radar_configs, 'evaluate_func': evaluate_func}
        _, obj, ecr, jmin, elapsed, corr = run_ablation(cfg, f"J={J}")

        results[J] = {'ecr': ecr, 'jmin': jmin, 'n_sols': len(ecr),
                      'corr': corr, 'time': elapsed}

    print(f"\n  J     Sols  ECR Range         r")
    for J, r in sorted(results.items()):
        print(f"  J={J:<3}  {r['n_sols']:<5} [{r['ecr'].min():.3f},{r['ecr'].max():.3f}]   {r['corr']:.3f}")

    return results


def _flatten_npz_payload(results, prefix=""):
    payload = {}
    for key, value in results.items():
        safe_key = f"{prefix}{key}".replace(" ", "_").replace("-", "_")
        if isinstance(value, np.ndarray):
            payload[safe_key] = value
        elif isinstance(value, (int, float, np.integer, np.floating)):
            payload[safe_key] = np.asarray(value)
        elif isinstance(value, dict):
            payload.update(_flatten_npz_payload(value, f"{safe_key}_"))
    return payload


def save_results(results, name, output_dir=None):
    """Save raw results as .npz for later analysis."""
    if output_dir is None:
        output_dir = os.path.join(PROJECT_ROOT, 'results')
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f'ablation_{name}.npz')
    payload = _flatten_npz_payload(results)
    np.savez(path, **payload)
    print(f"  Results saved: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ablation', default='all',
                       choices=['propagation','transform','normalization','region','radar_count','all'])
    parser.add_argument('--output-dir', default=os.path.join(PROJECT_ROOT, 'results'))
    parser.add_argument('--figure-dir', default=None)
    args = parser.parse_args()

    print("\n" + "#"*60)
    print(f"# MOPSO-DT Ablation Studies: {args.ablation}")
    print("#"*60)

    os.makedirs(args.output_dir, exist_ok=True)
    if args.figure_dir:
        os.makedirs(args.figure_dir, exist_ok=True)

    if args.ablation in ('propagation', 'all'):
        r = ablation_propagation()
        save_results(r, 'propagation', args.output_dir)

    if args.ablation in ('transform', 'all'):
        r = ablation_transform()
        save_results(r, 'transform', args.output_dir)

    if args.ablation in ('normalization', 'all'):
        r = ablation_normalization()
        save_results(r, 'normalization', args.output_dir)

    if args.ablation in ('region', 'all'):
        r = ablation_region()
        save_results(r, 'region', args.output_dir)

    if args.ablation in ('radar_count', 'all'):
        r = ablation_radar_count()
        save_results(r, 'radar_count', args.output_dir)

    print("\n" + "#"*60)
    print("# Ablation Complete")
    print("#"*60)
