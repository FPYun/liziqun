"""
大规模实验：1000km x 1000km，100台雷达，复杂区域

使用带孔洞/障碍物的复杂部署区域，测试 MOPSO-DT 在大规模高维场景下的优化能力。
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
from src.benchmarks import get_extreme_points, sample_representative_solutions
from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon

# ============================================================================
# 参数配置
# ============================================================================
REGION_SIZE = 1000       # km
J = 100                  # 雷达数量
N_P = 80                 # 粒子数
T_MAX = 100              # 迭代次数
GRID_SIZE = 40           # 任务点网格间距 (km) — 共约 (1000/40+1)^2 = 676 点
BETA = 0.008             # 检测概率衰减系数（更高 = 覆盖更难）
P0 = 0.90                # 初始检测概率
P_MIN = 0.75             # 最小检测门限

SAVE_DIR = os.path.join(PROJECT_ROOT, 'figures')
os.makedirs(SAVE_DIR, exist_ok=True)

def safe_print(*args, **kwargs):
    """防止 Windows GBK 编码错误"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        print(*(str(a).encode('ascii', errors='replace').decode('ascii') for a in args), **kwargs)

safe_print("#" * 70)
safe_print(f"# Large-scale experiment: {REGION_SIZE}km x {REGION_SIZE}km, {J} radars")
safe_print(f"# N_P={N_P}, T_max={T_MAX}, beta={BETA}")
safe_print("#" * 70)

# ============================================================================
# 1. 构建复杂部署区域（带孔洞）
# ============================================================================
safe_print("\n[1] Building complex deployment region...", end=' ', flush=True)
t0 = time.time()

# 1000x1000 外框 + 5个孔洞（模拟湖泊/禁区/山脉）
outer = [(0, 0), (REGION_SIZE, 0), (REGION_SIZE, REGION_SIZE), (0, REGION_SIZE)]
holes = [
    # 中心大城市（不能部署）
    [(400, 400), (600, 400), (600, 600), (400, 600)],
    # 左下湖泊
    [(50, 50), (180, 80), (200, 200), (80, 220)],
    # 右上禁区
    [(750, 700), (920, 720), (900, 900), (720, 880)],
    # 左上山区
    [(100, 700), (300, 680), (280, 880), (120, 900)],
    # 右下河流
    [(650, 150), (850, 100), (880, 300), (700, 320)],
]
region = ShapelyPolygon(outer, holes)

decomposer = DeploymentRegionDecomposer(verbose=False)
polygons, codes, n_bits = decomposer.decompose(region)
N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
safe_print(f"Done ({time.time()-t0:.1f}s) - {len(polygons)} convex polygons, N_bin={N_bin}")

# ============================================================================
# 2. 生成雷达配置和任务点
# ============================================================================
safe_print("[2] Generating radar configs and task points...", end=' ', flush=True)
radar_configs = [
    RadarConfig(P0=P0, P_min=P_MIN, beta=BETA, is_air=True)
    for _ in range(J)
]
task_points = generate_uniform_task_points(region, grid_size=GRID_SIZE)
safe_print(f"{len(task_points)} task points (grid={GRID_SIZE}km)")

# 估算：beta=0.008 时，P_detect > 0.75 的有效距离
# 0.9 * exp(-0.008 * d) = 0.75 -> d = ln(0.9/0.75)/0.008 ≈ 22.8 km
# 100台雷达覆盖：100 * π * 22.8^2 ≈ 163,000 km^2，仅占 1,000,000 km^2 的 16.3%
eff_range = np.log(P0 / P_MIN) / BETA
max_cover_area = J * np.pi * eff_range**2 / 1e6
safe_print(f"    有效探测距离: {eff_range:.0f} km")
safe_print(f"    100台雷达理论最大覆盖: {max_cover_area:.1f}M km2 / 1M km2 = {max_cover_area*100:.0f}%")

# ============================================================================
# 3. MOPSO 优化
# ============================================================================
safe_print(f"[3] MOPSO optimization (J={J}, N_bin={N_bin}, N_P={N_P}, T_max={T_MAX})...")
safe_print(f"    Decision space: continuous({2*J}d) + discrete({J*N_bin}d) = {2*J + J*N_bin}d")

evaluate_func = create_normalized_evaluate_function(
    task_points, radar_configs, polygons, J, N_bin, J_max_ref=0.00005
)

mopso = MOPSO_DT(
    J=J, N_bin=N_bin, evaluate_func=evaluate_func,
    N_P=N_P, T_max=T_MAX, c_1=2.0, c_2=2.0, p_c=0.9,
    archive_size=100, verbose=True,
    w_strategy='standard', p_m_base=0.01, select_gb='crowding'
)

t_opt_start = time.time()
archive, stats = mopso.optimize()
t_opt = time.time() - t_opt_start

safe_print(f"\n    Optimization done: {t_opt:.1f}s ({t_opt/60:.1f} min)")
safe_print(f"    Pareto solutions: {len(archive)}")

if len(archive) == 0:
    safe_print("ERROR: No Pareto solutions found!")
    sys.exit(1)

# ============================================================================
# 4. 后处理：计算每个解的 ECR 和 J_min
# ============================================================================
safe_print("[4] Post-processing: computing physical objective values...", end=' ', flush=True)
t1 = time.time()

objectives = np.array([e['objectives'] for e in archive])
ecr_vals, j_vals = [], []
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

ecr_arr = np.array(ecr_vals)
j_arr = np.array(j_vals)
safe_print(f"Done ({time.time()-t1:.1f}s)")

best_cov_idx, best_int_idx, knee_idx = get_extreme_points(objectives)

safe_print(f"\n    Objective space (f1=1-ECR, f2=J_norm):")
safe_print(f"      f1: [{objectives[:,0].min():.4f}, {objectives[:,0].max():.4f}]")
safe_print(f"      f2: [{objectives[:,1].min():.4f}, {objectives[:,1].max():.4f}]")
safe_print(f"\n    Physical space:")
safe_print(f"      ECR:       [{ecr_arr.min():.4f}, {ecr_arr.max():.4f}]")
safe_print(f"      J_min:     [{j_arr.min():.6e}, {j_arr.max():.6e}]")
safe_print(f"      Best coverage: ECR={ecr_arr[best_cov_idx]:.4f}, J_min={j_arr[best_cov_idx]:.6e}")
safe_print(f"      Best jamming:  ECR={ecr_arr[best_int_idx]:.4f}, J_min={j_arr[best_int_idx]:.6e}")
if knee_idx is not None:
    safe_print(f"      Knee (balance): ECR={ecr_arr[knee_idx]:.4f}, J_min={j_arr[knee_idx]:.6e}")

# ============================================================================
# 5. 综合可视化
# ============================================================================
safe_print("[5] Generating visualizations...", end=' ', flush=True)

ecr_unique = len(set(f"{v:.6f}" for v in ecr_vals))
j_unique = len(set(f"{v:.6e}" for v in j_vals))

fig = plt.figure(figsize=(20, 14))

# ---- 5a. Pareto 前沿 (左上) ----
ax1 = fig.add_subplot(2, 3, 1)
colors = plt.cm.RdYlGn(np.linspace(0.3, 1, len(objectives)))
ax1.scatter(objectives[:, 0], objectives[:, 1], c=colors,
            alpha=0.85, s=60, edgecolors='black', linewidth=0.3, zorder=3)
for idx, label, clr, offset in [
    (best_cov_idx, 'Best Coverage', 'darkred', (15, 15)),
    (best_int_idx, 'Best Jamming', 'darkblue', (-50, -20)),
]:
    ax1.scatter(objectives[idx, 0], objectives[idx, 1],
                s=180, marker='D', edgecolors='black', linewidth=1.5,
                facecolors=clr, zorder=5, alpha=0.9)
    ax1.annotate(label, (objectives[idx, 0], objectives[idx, 1]),
                 xytext=offset, textcoords='offset points', fontsize=9,
                 color=clr, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=clr, lw=1.2))
if knee_idx is not None:
    ax1.scatter(objectives[knee_idx, 0], objectives[knee_idx, 1],
                s=200, marker='*', edgecolors='black', linewidth=1.5,
                facecolors='gold', zorder=5)
    ax1.annotate('Knee', (objectives[knee_idx, 0], objectives[knee_idx, 1]),
                 xytext=(20, -25), textcoords='offset points', fontsize=9,
                 color='darkgreen', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='darkgreen', lw=1.2))
ax1.set_xlabel('f1 = 1 - ECR', fontsize=11)
ax1.set_ylabel('f2 = J_norm', fontsize=11)
ax1.set_title(f'Pareto Front ({len(archive)} solutions, {ecr_unique} unique)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)

# ---- 5b. ECR vs J_min 物理空间 (中上) ----
ax2 = fig.add_subplot(2, 3, 2)
ax2.scatter(ecr_arr, j_arr, c=plt.cm.RdYlGn(np.linspace(0.3, 1, len(ecr_arr))),
            s=60, alpha=0.8, edgecolors='black', linewidth=0.3)
ax2.scatter(ecr_arr[best_cov_idx], j_arr[best_cov_idx],
            s=150, marker='D', edgecolors='black', linewidth=1.5,
            facecolors='darkred', zorder=5, label='Best Coverage')
ax2.scatter(ecr_arr[best_int_idx], j_arr[best_int_idx],
            s=150, marker='D', edgecolors='black', linewidth=1.5,
            facecolors='darkblue', zorder=5, label='Best Jamming')
if knee_idx is not None:
    ax2.scatter(ecr_arr[knee_idx], j_arr[knee_idx],
                s=180, marker='*', edgecolors='black', linewidth=1.5,
                facecolors='gold', zorder=5, label='Knee')
ax2.set_xlabel('ECR', fontsize=11)
ax2.set_ylabel('J_min (W/m^2)', fontsize=11)
ax2.set_title('ECR vs J_min (Physical Space)', fontsize=13, fontweight='bold')
ax2.legend(fontsize=8, loc='best')
ax2.grid(True, alpha=0.3)

# ---- 5c. 收敛曲线 (右上) ----
ax3 = fig.add_subplot(2, 3, 3)
archive_sizes = stats.get('archive_sizes', [])
if archive_sizes:
    ax3.plot(range(1, len(archive_sizes)+1), archive_sizes,
             'b-', linewidth=1.5, alpha=0.8)
    ax3.fill_between(range(1, len(archive_sizes)+1), 0, archive_sizes, alpha=0.15)
ax3.set_xlabel('Iteration', fontsize=11)
ax3.set_ylabel('Archive Size', fontsize=11)
ax3.set_title('Convergence: Archive Size vs Iteration', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)

# ---- 5d-f. 三个代表性部署方案 (下排) ----
if knee_idx is not None:
    sample_indices = [best_cov_idx, knee_idx, best_int_idx]
else:
    sample_indices = [best_cov_idx, best_int_idx // 2, best_int_idx]

titles_deploy = ['Best Coverage', 'Knee (Balance)', 'Best Jamming']

for i_sub, (si, sub_title) in enumerate(zip(sample_indices, titles_deploy)):
    ax = fig.add_subplot(2, 3, 4 + i_sub)

    # 画区域（含孔洞）
    for poly in polygons:
        x, y = poly.exterior.xy
        ax.fill(x, y, alpha=0.15, color='lightblue', edgecolor='gray', linewidth=0.3)
    # 画孔洞轮廓
    for hole in holes:
        hx, hy = zip(*hole)
        ax.fill(hx, hy, alpha=0.3, color='white', edgecolor='darkgray', linewidth=0.5, linestyle='--')

    # 任务点（采样减少密度）
    tx = [t.x for t in task_points[::2]]
    ty = [t.y for t in task_points[::2]]
    ax.scatter(tx, ty, c='lightgray', s=1, alpha=0.3)

    # 雷达位置
    entry = archive[si]
    cont = entry['continuous'].reshape(J, 2).flatten()
    bin_ = entry['binary']
    pos = np.array(decode_particle(cont, bin_, J, N_bin, polygons))
    ax.scatter(pos[:, 0], pos[:, 1], c='red', s=25, marker='^',
               edgecolors='darkred', linewidth=0.3, zorder=5)

    ecr_si = ecr_arr[si]
    jm_si = j_arr[si]
    ax.set_title(f'{sub_title}\nECR={ecr_si:.4f}, J_min={jm_si:.4e}',
                 fontsize=11, fontweight='bold')
    ax.set_xlim(-20, REGION_SIZE + 20)
    ax.set_ylim(-20, REGION_SIZE + 20)
    ax.set_xlabel('X (km)', fontsize=9)
    ax.set_ylabel('Y (km)', fontsize=9)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

plt.tight_layout(pad=2.5)
fig_path = os.path.join(SAVE_DIR, 'large_scale_1000km_100radars.png')
plt.savefig(fig_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
safe_print("Done")

# ============================================================================
# 6. 汇总报告
# ============================================================================
hv = 0.0
sorted_idx = np.argsort(objectives[:, 0])
f1_s = objectives[sorted_idx, 0]; f2_s = objectives[sorted_idx, 1]
for k in range(1, len(f1_s)):
    hv += (f1_s[k] - f1_s[k-1]) * (1 - f2_s[k])
hv += (1 - f1_s[-1]) * (1 - f2_s[-1])

safe_print("\n" + "=" * 70)
safe_print("  Experiment Results Summary")
safe_print("=" * 70)
safe_print(f"  Problem scale:     {REGION_SIZE}km x {REGION_SIZE}km, {J} radars")
safe_print(f"  Decision dimension:{2*J + J*N_bin}")
safe_print(f"  Task points:       {len(task_points)}")
safe_print(f"  Detection range:   {eff_range:.0f} km (beta={BETA})")
safe_print(f"  MOPSO params:      N_P={N_P}, T_max={T_MAX}, strategy=standard")
safe_print(f"  Runtime:           {t_opt:.1f}s ({t_opt/60:.1f} min)")
safe_print(f"  Pareto solutions:  {len(archive)}")
safe_print(f"  ECR range:         [{ecr_arr.min():.4f}, {ecr_arr.max():.4f}]")
safe_print(f"  J_min range:       [{j_arr.min():.6e}, {j_arr.max():.6e}]")
safe_print(f"  Best ECR:          {ecr_arr[best_cov_idx]:.4f}")
safe_print(f"  Best J_min:        {j_arr[best_int_idx]:.6e}")
safe_print(f"  Hypervolume:       {hv:.4f}")
safe_print(f"  Figure saved to:   large_scale_1000km_100radars.png")
safe_print("=" * 70)
