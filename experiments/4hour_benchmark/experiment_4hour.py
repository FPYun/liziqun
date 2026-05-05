"""
4-Hour MOPSO-DT CPU+GPU Hybrid Benchmark Suite

4 部分实验：
  1. 可扩展性分析 (J=10~120)
  2. 消融实验 (3 改进组件贡献)
  3. 区域鲁棒性 (5 种形状)
  4. 参数敏感性 (N_P / T_max / p_c)

用法:
  python experiment_4hour.py          # 完整运行 (~4h)
  python experiment_4hour.py --quick  # 快速验证 (~2min)
"""

import numpy as np
import matplotlib.pyplot as plt
import time, sys, os, json, argparse, logging
from datetime import datetime
from collections import defaultdict

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.decomposition import DeploymentRegionDecomposer
from src.evaluation import (
    RadarConfig, TaskPoint, generate_uniform_task_points,
    calculate_ecr, calculate_jamming_density,
    decode_particle, create_normalized_evaluate_function,
    GPU_AVAILABLE,
)
from src.hybrid_mopso import (
    HybridMOPSO,
    create_cpu_evaluate_function,
    create_cpu_normalized_evaluate_function,
)
from src.mopso import MOPSO_DT
from src.benchmarks import find_knee_point, get_extreme_points
from shapely.geometry import Polygon as ShapelyPolygon

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(THIS_DIR, 'figures')
RESULT_DIR = os.path.join(THIS_DIR, 'results')
LOG_DIR = os.path.join(THIS_DIR, 'logs')
for d in [FIG_DIR, RESULT_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================================================================
# 辅助函数
# ============================================================================

def _safe_print(msg):
    """安全打印，处理 Windows GBK 编码问题"""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))

def compute_hypervolume(objectives):
    """梯形法计算双目标超体积（参考点: (1, 1)）"""
    if len(objectives) < 2:
        return 0.0
    sorted_idx = np.argsort(objectives[:, 0])
    f1 = objectives[sorted_idx, 0]
    f2 = objectives[sorted_idx, 1]
    hv = 0.0
    for k in range(1, len(f1)):
        hv += (f1[k] - f1[k - 1]) * (1.0 - f2[k])
    hv += (1.0 - f1[-1]) * (1.0 - f2[-1])
    return float(hv)


def compute_real_metrics(archive, polygons, task_points, radar_configs, J, N_bin):
    """解码档案中每个解，计算真实 ECR / J_min"""
    ecr_vals, j_vals = [], []
    for entry in archive:
        sol = np.concatenate([entry['continuous'].reshape(-1, 2), entry['binary']], axis=1)
        cont = sol[:, :2].flatten()
        bin_ = sol[:, 2:2 + N_bin]
        pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
        ecr = calculate_ecr(pos, task_points, radar_configs,
                            convex_polygons=polygons, binary_codes=bin_,
                            continuous_coords=cont.reshape(J, 2))
        jm = calculate_jamming_density(pos, task_points, radar_configs,
                                        convex_polygons=polygons, binary_codes=bin_,
                                        continuous_coords=cont.reshape(J, 2))
        ecr_vals.append(ecr)
        j_vals.append(jm)
    ecr_arr = np.array(ecr_vals)
    j_arr = np.array(j_vals)
    objectives = np.array([e['objectives'] for e in archive])
    corr = float(np.corrcoef(ecr_arr, j_arr)[0, 1]) if len(archive) > 2 else 0.0
    knee = find_knee_point(objectives) if len(objectives) >= 3 else None
    return {
        'ecr_array': ecr_arr, 'j_array': j_arr,
        'ecr_min': float(ecr_arr.min()), 'ecr_max': float(ecr_arr.max()),
        'j_min': float(j_arr.min()), 'j_max': float(j_arr.max()),
        'correlation': corr, 'knee_idx': knee,
    }


def create_region(shape, size_km):
    """创建不同形状的部署区域"""
    if shape == 'square':
        return ShapelyPolygon([(0, 0), (size_km, 0), (size_km, size_km), (0, size_km)])
    elif shape == 'lshape':
        s = size_km
        t = s / 3
        return ShapelyPolygon([
            (0, 0), (s, 0), (s, t), (t, t), (t, s), (0, s)
        ])
    elif shape == 'with_holes':
        s = size_km
        h = s / 3
        outer = ShapelyPolygon([(0, 0), (s, 0), (s, s), (0, s)])
        hole = ShapelyPolygon([(h, h), (2 * h, h), (2 * h, 2 * h), (h, 2 * h)])
        return outer.difference(hole)
    elif shape == 'narrow':
        w = size_km
        h = size_km / 6
        return ShapelyPolygon([(0, 0), (w, 0), (w, h), (0, h)])
    elif shape == 'star':
        cx, cy = size_km / 2, size_km / 2
        r_outer = size_km / 2
        r_inner = size_km / 4
        n_pts = 8
        pts = []
        for i in range(2 * n_pts):
            angle = np.pi * i / n_pts - np.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            pts.append((cx + r * np.cos(angle), cy + r * np.sin(angle)))
        return ShapelyPolygon(pts)
    else:
        raise ValueError(f"未知区域形状: {shape}")


def create_problem(region, J, grid_size, beta=0.02, P0=0.95, P_min=0.8, is_air=True):
    """创建问题实例：分解区域、生成配置和任务点"""
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))

    radar_configs = [
        RadarConfig(P0=P0, P_min=P_min, beta=beta, is_air=is_air)
        for _ in range(J)
    ]
    task_points = generate_uniform_task_points(region, grid_size=grid_size)

    return polygons, N_bin, radar_configs, task_points


def run_single(region, J, N_P, T_max, grid_size, w_strategy, p_m_base, select_gb,
               seed, beta=0.02, P0=0.95, P_min=0.8, is_air=True,
               archive_size=100, c_1=2.0, c_2=2.0, p_c=0.9, use_hybrid=True,
               gpu_fraction=0.8, n_cpu_workers=4):
    """执行单次优化运行，返回结果字典"""
    np.random.seed(seed)

    polygons, N_bin, radar_configs, task_points = create_problem(
        region, J, grid_size, beta=beta, P0=P0, P_min=P_min, is_air=is_air
    )

    # GPU 评估函数（CuPy 加速）
    gpu_eval = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.005
    )
    # CPU 评估函数（纯 NumPy）
    cpu_eval = create_cpu_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.005
    )

    mopso_cls = HybridMOPSO if use_hybrid else MOPSO_DT
    mopso_kwargs = dict(
        J=J, N_bin=N_bin, evaluate_func=gpu_eval,
        N_P=N_P, T_max=T_max, c_1=c_1, c_2=c_2, p_c=p_c,
        archive_size=archive_size, verbose=False,
        w_strategy=w_strategy, p_m_base=p_m_base, select_gb=select_gb,
    )
    if use_hybrid:
        mopso_kwargs['cpu_evaluate_func'] = cpu_eval
        mopso_kwargs['gpu_fraction'] = gpu_fraction
        mopso_kwargs['n_cpu_workers'] = n_cpu_workers

    mopso = mopso_cls(**mopso_kwargs)
    t0 = time.time()
    archive, stats = mopso.optimize()
    elapsed = time.time() - t0

    if len(archive) == 0:
        return {'error': 'no solutions', 'time': elapsed}

    objectives = np.array([e['objectives'] for e in archive])
    hv = compute_hypervolume(objectives)
    metrics = compute_real_metrics(archive, polygons, task_points, radar_configs, J, N_bin)

    return {
        'n_solutions': len(archive),
        'time': elapsed,
        'hypervolume': hv,
        'f1_min': float(objectives[:, 0].min()),
        'f1_max': float(objectives[:, 0].max()),
        'f2_min': float(objectives[:, 1].min()),
        'f2_max': float(objectives[:, 1].max()),
        **metrics,
    }


# ============================================================================
# 可视化
# ============================================================================

def plot_scalability(results, save_path):
    """Part 1: 可扩展性分析 — 5 面板图"""
    J_vals = sorted(results.keys())
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()

    # 汇总各 J 的 mean±std
    times_mean, times_std = [], []
    hv_mean, hv_std = [], []
    n_sol_mean, n_sol_std = [], []
    ecr_min_mean, ecr_max_mean = [], []
    j_min_mean = []

    for J in J_vals:
        runs = results[J]
        times = [r['time'] for r in runs if 'time' in r]
        hvs = [r['hypervolume'] for r in runs if 'hypervolume' in r]
        nsols = [r['n_solutions'] for r in runs if 'n_solutions' in r]
        ecr_min = [r['ecr_min'] for r in runs if 'ecr_min' in r]
        ecr_max = [r['ecr_max'] for r in runs if 'ecr_max' in r]
        j_min = [r['j_min'] for r in runs if 'j_min' in r]

        times_mean.append(np.mean(times)); times_std.append(np.std(times))
        hv_mean.append(np.mean(hvs)); hv_std.append(np.std(hvs))
        n_sol_mean.append(np.mean(nsols)); n_sol_std.append(np.std(nsols))
        ecr_min_mean.append(np.mean(ecr_min)); ecr_max_mean.append(np.mean(ecr_max))
        j_min_mean.append(np.mean(j_min))

    ax = axes[0]
    ax.errorbar(J_vals, times_mean, yerr=times_std, marker='o', capsize=4, color='steelblue')
    ax.set_xlabel('J (Number of Radars)'); ax.set_ylabel('Runtime (s)')
    ax.set_title('Runtime vs J'); ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.errorbar(J_vals, hv_mean, yerr=hv_std, marker='s', capsize=4, color='coral')
    ax.set_xlabel('J'); ax.set_ylabel('Hypervolume')
    ax.set_title('Hypervolume vs J'); ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.errorbar(J_vals, n_sol_mean, yerr=n_sol_std, marker='^', capsize=4, color='seagreen')
    ax.set_xlabel('J'); ax.set_ylabel('Pareto Solutions')
    ax.set_title('Archive Size vs J'); ax.grid(True, alpha=0.3)

    ax = axes[3]
    ax.fill_between(J_vals, ecr_min_mean, ecr_max_mean, alpha=0.3, color='steelblue')
    ax.plot(J_vals, ecr_min_mean, 'o-', color='navy', label='ECR min')
    ax.plot(J_vals, ecr_max_mean, 's-', color='darkred', label='ECR max')
    ax.set_xlabel('J'); ax.set_ylabel('ECR')
    ax.set_title('ECR Range vs J'); ax.legend(); ax.grid(True, alpha=0.3)

    ax = axes[4]
    ax.errorbar(J_vals, j_min_mean, marker='D', capsize=4, color='purple')
    ax.set_xlabel('J'); ax.set_ylabel('J_min')
    ax.set_title('J_min vs J'); ax.grid(True, alpha=0.3)

    axes[5].set_visible(False)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    _safe_print(f"  Figure saved: {save_path}")


def plot_ablation(results, save_path):
    """Part 2: 消融实验 — 分组柱状图"""
    configs = ['A. Baseline', 'B. +Standard W', 'C. +Crowding GB', 'D. Full']
    scenarios = ['Small', 'Medium', 'Large']
    metrics_names = ['hypervolume', 'n_solutions', 'ecr_max']

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    colors = ['#b0bec5', '#64b5f6', '#ffb74d', '#81c784']

    for mi, metric in enumerate(metrics_names):
        ax = axes[mi]
        x = np.arange(len(scenarios))
        width = 0.2
        for ci, cfg in enumerate(configs):
            vals = []
            for si, sc in enumerate(scenarios):
                runs = results.get(cfg, {}).get(sc, [])
                mv = np.mean([r[metric] for r in runs if metric in r]) if runs else 0
                vals.append(mv)
            offset = (ci - 1.5) * width
            ax.bar(x + offset, vals, width, label=cfg, color=colors[ci], edgecolor='black', linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios)
        ax.set_title(metric.replace('_', ' ').title())
        ax.grid(True, alpha=0.3, axis='y')

    axes[0].legend(fontsize=7, loc='upper left')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    _safe_print(f"  Figure saved: {save_path}")


def plot_regions(region_results, save_path):
    """Part 3: 区域鲁棒性 — 5 种区域部署方案"""
    shapes = list(region_results.keys())
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()

    for idx, shape in enumerate(shapes):
        ax = axes[idx]
        data = region_results[shape]
        if not data:
            ax.set_title(f'{shape} (no data)')
            continue

        # 取第一个 seed 的结果绘制部署
        best_run = data[0]
        polygons = best_run.get('_polygons', [])
        task_points = best_run.get('_task_points', [])

        for poly in polygons:
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.2, color='lightblue', edgecolor='blue', linewidth=0.5)

        if task_points:
            tx = [t.x for t in task_points]
            ty = [t.y for t in task_points]
            ax.scatter(tx, ty, c='gray', s=1, alpha=0.3)

        ecr_mean = np.mean([r['ecr_max'] for r in data if 'ecr_max' in r])
        hv_mean = np.mean([r['hypervolume'] for r in data if 'hypervolume' in r])
        ax.set_title(f'{shape}\nECR max={ecr_mean:.3f}, HV={hv_mean:.3f}')
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

    # 汇总柱状图
    ax = axes[5]
    metrics_vals = {s: [] for s in shapes}
    for shape in shapes:
        runs = region_results[shape]
        metrics_vals[shape] = np.mean([r['hypervolume'] for r in runs if 'hypervolume' in r])
    bars = ax.bar(shapes, [metrics_vals[s] for s in shapes],
                   color=plt.cm.Set3(np.linspace(0, 1, len(shapes))), edgecolor='black')
    ax.set_ylabel('Hypervolume')
    ax.set_title('HV by Region Shape')
    ax.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    _safe_print(f"  Figure saved: {save_path}")


def plot_sensitivity(sens_results, save_path):
    """Part 4: 参数敏感性 — N_P / T_max / p_c 影响曲线"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

    # N_P 扫描
    ax = axes[0]
    np_vals = sorted(sens_results['N_P'].keys())
    hv_means = [np.mean([r['hypervolume'] for r in sens_results['N_P'][v] if 'hypervolume' in r]) for v in np_vals]
    time_means = [np.mean([r['time'] for r in sens_results['N_P'][v] if 'time' in r]) for v in np_vals]
    ax2_0 = ax.twinx()
    ax.bar(np_vals, hv_means, width=max(np_vals)*0.08, color='steelblue', alpha=0.7, label='HV')
    ax2_0.plot(np_vals, time_means, 'o-', color='coral', linewidth=2, label='Time')
    ax.set_xlabel('N_P'); ax.set_ylabel('Hypervolume'); ax2_0.set_ylabel('Time (s)')
    ax.set_title('N_P Sensitivity'); ax.grid(True, alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_0.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    # T_max 扫描
    ax = axes[1]
    tm_vals = sorted(sens_results['T_max'].keys())
    hv_means = [np.mean([r['hypervolume'] for r in sens_results['T_max'][v] if 'hypervolume' in r]) for v in tm_vals]
    time_means = [np.mean([r['time'] for r in sens_results['T_max'][v] if 'time' in r]) for v in tm_vals]
    ax2_1 = ax.twinx()
    ax.bar(tm_vals, hv_means, width=max(tm_vals)*0.08, color='steelblue', alpha=0.7, label='HV')
    ax2_1.plot(tm_vals, time_means, 's-', color='coral', linewidth=2, label='Time')
    ax.set_xlabel('T_max'); ax.set_ylabel('Hypervolume'); ax2_1.set_ylabel('Time (s)')
    ax.set_title('T_max Sensitivity'); ax.grid(True, alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_1.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    # p_c 扫描
    ax = axes[2]
    pc_vals = sorted(sens_results['p_c'].keys())
    hv_means = [np.mean([r['hypervolume'] for r in sens_results['p_c'][v] if 'hypervolume' in r]) for v in pc_vals]
    nsol_means = [np.mean([r['n_solutions'] for r in sens_results['p_c'][v] if 'n_solutions' in r]) for v in pc_vals]
    ax2_2 = ax.twinx()
    ax.bar(pc_vals, hv_means, width=0.05, color='steelblue', alpha=0.7, label='HV')
    ax2_2.plot(pc_vals, nsol_means, 'D-', color='seagreen', linewidth=2, label='Solutions')
    ax.set_xlabel('p_c'); ax.set_ylabel('Hypervolume'); ax2_2.set_ylabel('Solutions')
    ax.set_title('p_c Sensitivity'); ax.grid(True, alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    _safe_print(f"  Figure saved: {save_path}")


# ============================================================================
# 实验各部分
# ============================================================================

def run_part1_scalability(quick=False):
    """Part 1: 可扩展性分析"""
    print("\n" + "=" * 70)
    print("Part 1: Scalability Analysis")
    print("=" * 70)

    if quick:
        J_list = [10, 20]
        N_P, T_max, grid = 10, 5, 10
        seeds = [42]
    else:
        J_list = [10, 20, 40, 80, 120]
        N_P, T_max, grid = 100, 300, 40
        seeds = [42, 123, 777]

    region = create_region('square', 500)
    results = defaultdict(list)

    for J in J_list:
        print(f"\n  J={J} ({len(seeds)} seeds)...")
        for seed in seeds:
            r = run_single(region, J, N_P, T_max, grid,
                           w_strategy='standard', p_m_base=0.01, select_gb='crowding',
                           seed=seed)
            results[J].append(r)
            status = f"{r['time']:.1f}s, {r.get('n_solutions', 0)} sols" if 'error' not in r else 'FAILED'
            print(f"    seed={seed}: {status}")

    plot_scalability(results, os.path.join(FIG_DIR, 'scalability.png'))
    return results


def run_part2_ablation(quick=False):
    """Part 2: 消融实验"""
    print("\n" + "=" * 70)
    print("Part 2: Ablation Study")
    print("=" * 70)

    configs = [
        ('A. Baseline',        'legacy',   0.0,  'random'),
        ('B. +Standard W',     'standard', 0.0,  'random'),
        ('C. +Crowding GB',    'standard', 0.0,  'crowding'),
        ('D. Full',            'standard', 0.01, 'crowding'),
    ]

    if quick:
        scenarios = [('Small', 200, 10, 10, 80, 5)]
        seeds = [42]
    else:
        scenarios = [
            ('Small',  200, 10, 30, 80, 400),
            ('Medium', 400, 30, 35, 80, 400),
            ('Large',  600, 50, 40, 80, 400),
        ]
        seeds = [42, 123, 777]

    results = {}

    for cfg_name, w_strat, p_m, gb_sel in configs:
        results[cfg_name] = {}
        print(f"\n  Config: {cfg_name}")
        for sc_name, size, J, grid, N_P, T_max in scenarios:
            print(f"    Scenario: {sc_name} ({size}km^2, J={J})")
            region = create_region('square', size)
            runs = []
            for seed in seeds:
                r = run_single(region, J, N_P, T_max, grid,
                               w_strategy=w_strat, p_m_base=p_m, select_gb=gb_sel,
                               seed=seed)
                runs.append(r)
                status = f"{r['time']:.1f}s, {r.get('n_solutions', 0)} sols" if 'error' not in r else 'FAILED'
                print(f"      seed={seed}: {status}")
            results[cfg_name][sc_name] = runs

    plot_ablation(results, os.path.join(FIG_DIR, 'ablation.png'))
    return results


def run_part3_regions(quick=False):
    """Part 3: 区域鲁棒性"""
    print("\n" + "=" * 70)
    print("Part 3: Region Robustness")
    print("=" * 70)

    if quick:
        shapes = ['square', 'lshape']
        seeds = [42]
        N_P, T_max, grid, J = 10, 5, 10, 10
    else:
        shapes = ['square', 'lshape', 'with_holes', 'narrow', 'star']
        seeds = [42, 123, 777, 999]
        N_P, T_max, grid, J = 100, 250, 40, 30

    region_results = {}

    for shape in shapes:
        print(f"\n  Shape: {shape}")
        region = create_region(shape, 300)
        runs = []
        for seed in seeds:
            r = run_single(region, J, N_P, T_max, grid,
                           w_strategy='standard', p_m_base=0.01, select_gb='crowding',
                           seed=seed)
            # 附带区域信息供绘图
            polygons, _, _, task_points = create_problem(region, J, grid)
            r['_polygons'] = polygons
            r['_task_points'] = task_points
            runs.append(r)
            status = f"{r['time']:.1f}s, {r.get('n_solutions', 0)} sols" if 'error' not in r else 'FAILED'
            print(f"    seed={seed}: {status}")
        region_results[shape] = runs

    plot_regions(region_results, os.path.join(FIG_DIR, 'regions.png'))
    return region_results


def run_part4_sensitivity(quick=False):
    """Part 4: 参数敏感性"""
    print("\n" + "=" * 70)
    print("Part 4: Parameter Sensitivity")
    print("=" * 70)

    region = create_region('square', 300)
    J = 30

    if quick:
        N_P_vals = [10, 30]
        T_max_vals = [5, 10]
        p_c_vals = [0.5, 0.9]
        seeds = [42]
        grid = 10
        base_N_P, base_T_max = 10, 5
    else:
        N_P_vals = [30, 60, 120]
        T_max_vals = [100, 200, 400]
        p_c_vals = [0.5, 0.7, 0.9]
        seeds = [42, 123, 777]
        grid = 35
        base_N_P, base_T_max = 80, 200

    results = {'N_P': {}, 'T_max': {}, 'p_c': {}}

    # N_P 扫描
    print("\n  N_P sweep:")
    for np_val in N_P_vals:
        print(f"    N_P={np_val}")
        runs = []
        for seed in seeds:
            r = run_single(region, J, np_val, base_T_max, grid,
                           w_strategy='standard', p_m_base=0.01, select_gb='crowding',
                           seed=seed)
            runs.append(r)
            status = f"{r['time']:.1f}s" if 'error' not in r else 'FAILED'
            print(f"      seed={seed}: {status}")
        results['N_P'][np_val] = runs

    # T_max 扫描
    print("\n  T_max sweep:")
    for tm_val in T_max_vals:
        print(f"    T_max={tm_val}")
        runs = []
        for seed in seeds:
            r = run_single(region, J, base_N_P, tm_val, grid,
                           w_strategy='standard', p_m_base=0.01, select_gb='crowding',
                           seed=seed)
            runs.append(r)
            status = f"{r['time']:.1f}s" if 'error' not in r else 'FAILED'
            print(f"      seed={seed}: {status}")
        results['T_max'][tm_val] = runs

    # p_c 扫描
    print("\n  p_c sweep:")
    for pc_val in p_c_vals:
        print(f"    p_c={pc_val}")
        runs = []
        for seed in seeds:
            r = run_single(region, J, base_N_P, base_T_max, grid,
                           w_strategy='standard', p_m_base=0.01, select_gb='crowding',
                           seed=seed, p_c=pc_val)
            runs.append(r)
            status = f"{r['time']:.1f}s" if 'error' not in r else 'FAILED'
            print(f"      seed={seed}: {status}")
        results['p_c'][pc_val] = runs

    plot_sensitivity(results, os.path.join(FIG_DIR, 'sensitivity.png'))
    return results


# ============================================================================
# 报告生成
# ============================================================================

def generate_report(all_results, quick):
    """生成 Markdown 实验报告"""
    lines = []
    lines.append("# MOPSO-DT 4-Hour Benchmark Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Mode: {'Quick' if quick else 'Full'}")
    lines.append(f"GPU Available: {GPU_AVAILABLE}")
    lines.append("")

    # Part 1 summary
    p1 = all_results.get('scalability', {})
    if p1:
        lines.append("## Part 1: Scalability")
        lines.append("| J | Runtime (s) | HV | Solutions | ECR Range |")
        lines.append("|---|------------|----|-----------|-----------|")
        for J in sorted(p1.keys()):
            runs = p1[J]
            times = [r['time'] for r in runs if 'time' in r]
            hvs = [r['hypervolume'] for r in runs if 'hypervolume' in r]
            nsols = [r['n_solutions'] for r in runs if 'n_solutions' in r]
            ecr_min = [r['ecr_min'] for r in runs if 'ecr_min' in r]
            ecr_max = [r['ecr_max'] for r in runs if 'ecr_max' in r]
            t_str = f"{np.mean(times):.1f}±{np.std(times):.1f}" if times else "N/A"
            hv_str = f"{np.mean(hvs):.4f}" if hvs else "N/A"
            ns_str = f"{np.mean(nsols):.0f}" if nsols else "N/A"
            ecr_str = f"[{np.mean(ecr_min):.3f}, {np.mean(ecr_max):.3f}]" if ecr_min else "N/A"
            lines.append(f"| {J} | {t_str} | {hv_str} | {ns_str} | {ecr_str} |")
        lines.append("")

    # Part 2 summary
    p2 = all_results.get('ablation', {})
    if p2:
        lines.append("## Part 2: Ablation Study")
        lines.append("| Config | Scenario | HV | Solutions | ECR Max |")
        lines.append("|--------|----------|----|-----------|--------|")
        for cfg_name in sorted(p2.keys()):
            for sc_name in sorted(p2[cfg_name].keys()):
                runs = p2[cfg_name][sc_name]
                hvs = np.mean([r['hypervolume'] for r in runs if 'hypervolume' in r]) if runs else 0
                nsols = np.mean([r['n_solutions'] for r in runs if 'n_solutions' in r]) if runs else 0
                ecr = np.mean([r['ecr_max'] for r in runs if 'ecr_max' in r]) if runs else 0
                lines.append(f"| {cfg_name} | {sc_name} | {hvs:.4f} | {nsols:.0f} | {ecr:.3f} |")
        lines.append("")

    # Part 3 summary
    p3 = all_results.get('regions', {})
    if p3:
        lines.append("## Part 3: Region Robustness")
        lines.append("| Shape | HV | ECR Max | J_min |")
        lines.append("|-------|----|---------|-------|")
        for shape in sorted(p3.keys()):
            runs = p3[shape]
            hvs = np.mean([r['hypervolume'] for r in runs if 'hypervolume' in r]) if runs else 0
            ecr = np.mean([r['ecr_max'] for r in runs if 'ecr_max' in r]) if runs else 0
            jm = np.mean([r['j_min'] for r in runs if 'j_min' in r]) if runs else 0
            lines.append(f"| {shape} | {hvs:.4f} | {ecr:.3f} | {jm:.4e} |")
        lines.append("")

    # Part 4 summary
    p4 = all_results.get('sensitivity', {})
    if p4:
        lines.append("## Part 4: Parameter Sensitivity")
        for param in ['N_P', 'T_max', 'p_c']:
            lines.append(f"\n### {param}")
            lines.append("| Value | HV | Time (s) | Solutions |")
            lines.append("|-------|----|---------|-----------|")
            for val in sorted(p4[param].keys()):
                runs = p4[param][val]
                hvs = np.mean([r['hypervolume'] for r in runs if 'hypervolume' in r]) if runs else 0
                times = np.mean([r['time'] for r in runs if 'time' in r]) if runs else 0
                nsols = np.mean([r['n_solutions'] for r in runs if 'n_solutions' in r]) if runs else 0
                lines.append(f"| {val} | {hvs:.4f} | {times:.1f} | {nsols:.0f} |")
        lines.append("")

    report_path = os.path.join(RESULT_DIR, 'experiment_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    _safe_print(f"\nReport saved: {report_path}")


def save_results_json(all_results, quick):
    """保存结构化 JSON 结果（去除不可序列化字段）"""
    def make_serializable(obj):
        if isinstance(obj, dict):
            return {str(k): make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_serializable(v) for v in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, defaultdict):
            return make_serializable(dict(obj))
        return obj

    clean = make_serializable(all_results)
    clean['_meta'] = {
        'mode': 'quick' if quick else 'full',
        'gpu_available': GPU_AVAILABLE,
        'timestamp': datetime.now().isoformat(),
    }
    json_path = os.path.join(RESULT_DIR, 'experiment_results.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(clean, f, indent=2, ensure_ascii=False, default=str)
    _safe_print(f"Results saved: {json_path}")


# ============================================================================
# 主入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='4-Hour MOPSO-DT Benchmark Suite')
    parser.add_argument('--quick', action='store_true', help='Quick validation mode (~2 min)')
    parser.add_argument('--part', type=int, choices=[1, 2, 3, 4], help='Run only specified part')
    args = parser.parse_args()

    quick = args.quick
    mode_str = "QUICK" if quick else "FULL"
    print(f"\n{'#' * 70}")
    print(f"# MOPSO-DT 4-Hour Benchmark — {mode_str} MODE")
    print(f"# GPU Available: {GPU_AVAILABLE}")
    print(f"{'#' * 70}")

    t_start = time.time()
    all_results = {}

    if args.part is None or args.part == 1:
        all_results['scalability'] = run_part1_scalability(quick=quick)

    if args.part is None or args.part == 2:
        all_results['ablation'] = run_part2_ablation(quick=quick)

    if args.part is None or args.part == 3:
        all_results['regions'] = run_part3_regions(quick=quick)

    if args.part is None or args.part == 4:
        all_results['sensitivity'] = run_part4_sensitivity(quick=quick)

    total_time = time.time() - t_start

    print(f"\n{'#' * 70}")
    print(f"# Benchmark Complete — Total: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"{'#' * 70}")

    generate_report(all_results, quick)
    save_results_json(all_results, quick)

    _safe_print("\nOutput files:")
    for f in sorted(os.listdir(FIG_DIR)):
        _safe_print(f"  figures/{f}")
    for f in sorted(os.listdir(RESULT_DIR)):
        _safe_print(f"  results/{f}")


if __name__ == "__main__":
    main()
