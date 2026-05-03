"""
基于参考论文参数的仿真实验脚本

参数对齐参考论文4.1节和4.2.2节：
- 区域: 300km × 300km
- 分辨率: 30×30网格 (10km间距, 900个任务点)
- 雷达: 8个节点，雷达方程模型
- MOPSO: N_P=50, T_max=500, c1=2, c2=2, p_c=0.5
- 检测模型: 雷达方程 SNR = (P_t * G^2 * λ^2 * σ) / ((4π)^3 * k * T0 * B * d^4)
- 干扰模型: J = P_t_jammer * G_t_jammer / (4π * d^2)
"""

import numpy as np
import matplotlib.pyplot as plt
import sys
import os
import time

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


def create_paper_radar_configs(n_radars=8):
    """
    创建参考论文对齐的雷达配置

    参考论文4.1节参数：
    - 雷达发射功率: 3kW
    - 天线增益: 50dB
    - 波长: 0.3m
    - RCS: 0.1m²
    - 带宽: 15MHz
    - 检测因子: 12.5dB
    - 最大探测距离: 60km
    - 干扰机功率: 150W
    - 干扰机增益: 30dB
    """
    configs = []
    for i in range(n_radars):
        config = RadarConfig(
            # 雷达方程参数（参考论文4.1节）
            P_t=3000.0,           # 3kW
            G_t_dB=50.0,          # 50dB
            wavelength=0.3,       # 0.3m
            sigma=0.1,            # 0.1m²
            bandwidth=15e6,       # 15MHz
            D0_dB=12.5,           # 12.5dB
            P_fa=1e-6,
            R_max=60.0,           # 60km
            # 干扰机参数
            jammer_P_t=150.0,     # 150W
            jammer_G_t_dB=30.0,   # 30dB
            # 使用雷达方程模型
            use_radar_equation=True,
            # 检测阈值
            P_min=0.5,
            # 位置类型（全部为地面节点）
            is_air=False
        )
        configs.append(config)
    return configs


def run_paper_experiment():
    """
    运行参考论文对齐的仿真实验

    实验设置：
    - 区域: 300km × 300km
    - 任务点: 10×10网格 (100个点, 30km间距)
    - 雷达: 8个节点
    - MOPSO: N_P=10, T_max=50, p_c=0.5
    """
    print("\n" + "=" * 70)
    print("参考论文对齐仿真实验")
    print("=" * 70)
    print("参数来源: 参考论文 4.1节 和 4.2.2节")
    print("区域: 300km × 300km")
    print("任务点: 10×10网格 (100个点, 30km间距)")
    print("雷达: 8个节点 (雷达方程模型)")
    print("MOPSO: N_P=10, T_max=50, p_c=0.5")
    print("=" * 70)

    # 创建区域
    region = ShapelyPolygon([(0, 0), (300, 0), (300, 300), (0, 300)])

    # 区域分解
    print("\n[1] 区域分解...")
    decomposer = DeploymentRegionDecomposer(verbose=False)
    polygons, codes, n_bits = decomposer.decompose(region)
    print(f"    分解得到 {len(polygons)} 个凸多边形")
    print(f"    二进制编码位数: {n_bits}")

    # 创建雷达配置
    print("\n[2] 创建雷达配置...")
    radar_configs = create_paper_radar_configs(n_radars=8)
    print(f"    雷达数量: {len(radar_configs)}")
    print(f"    发射功率: {radar_configs[0].P_t/1000:.1f} kW")
    print(f"    天线增益: {radar_configs[0].G_t_dB:.1f} dB")
    print(f"    最大探测距离: {radar_configs[0].R_max:.0f} km")
    print(f"    干扰机功率: {radar_configs[0].jammer_P_t:.0f} W")
    print(f"    干扰机增益: {radar_configs[0].jammer_G_t_dB:.0f} dB")

    # 生成任务点
    print("\n[3] 生成任务点...")
    task_points = generate_uniform_task_points(region, grid_size=10)
    print(f"    生成 {len(task_points)} 个任务点")
    print(f"    网格间距: 30 km")

    # MOPSO优化
    print("\n[4] MOPSO优化...")
    J = 8
    N_bin = max(1, int(np.ceil(np.log2(len(polygons)))))
    print(f"    J={J}, N_bin={N_bin}")
    print(f"    粒子数: 10, 最大迭代: 50")
    print(f"    c1=2, c2=2, p_c=0.5")
    print(f"    惯性权重: w = -0.4/50 * t + 0.4")

    # 计算J_max_ref用于归一化
    # 先估算J_min的量级
    test_config = radar_configs[0]
    d_test = 300.0  # 300km对角线距离
    G_jammer = 10 ** (test_config.jammer_G_t_dB / 10.0)
    J_est = test_config.jammer_P_t * G_jammer / (4 * np.pi * (d_test * 1000) ** 2)
    J_max_ref = J_est * 2  # 参考值
    print(f"    J_max_ref (归一化参考): {J_max_ref:.6e}")

    evaluate_func = create_normalized_evaluate_function(
        task_points, radar_configs, polygons, J, N_bin, J_max_ref=J_max_ref
    )

    mopso = MOPSO_DT(
        J=J, N_bin=N_bin, evaluate_func=evaluate_func,
        N_P=10, T_max=50, c_1=2.0, c_2=2.0,
        p_c=0.5, archive_size=50, verbose=False
    )

    print("\n    开始优化...")
    start_time = time.time()
    pareto_archive, stats = mopso.optimize()
    elapsed = time.time() - start_time
    print(f"    优化完成，耗时: {elapsed:.1f}秒")

    print(f"\n[5] 优化结果:")
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

    print(f"    f1 (1-ECR) 范围: [{objectives[:, 0].min():.4f}, {objectives[:, 0].max():.4f}]")
    print(f"    f2 (J_norm) 范围: [{objectives[:, 1].min():.4f}, {objectives[:, 1].max():.4f}]")
    print(f"    ECR 范围: [{ecr_array.min():.4f}, {ecr_array.max():.4f}]")
    print(f"    J_min 范围: [{j_min_array.min():.6e}, {j_min_array.max():.6e}]")

    # 拐点检测
    if len(objectives) >= 3:
        knee_idx = find_knee_point(objectives)
        print(f"    拐点 (Knee): ECR={1-objectives[knee_idx,0]:.4f}, "
              f"J_norm={objectives[knee_idx,1]:.6f}")

    # 相关性分析
    if len(ecr_array) > 2:
        correlation = np.corrcoef(ecr_array, j_min_array)[0, 1]
        print(f"    ECR-J_min 相关系数: {correlation:.4f}")

    return {
        'pareto_solutions': pareto_solutions,
        'objectives': objectives,
        'ecr_array': ecr_array,
        'j_min_array': j_min_array,
        'polygons': polygons,
        'task_points': task_points,
        'radar_configs': radar_configs,
        'J': J,
        'N_bin': N_bin,
        'elapsed': elapsed
    }


def visualize_results(results):
    """生成论文级可视化图片"""
    print("\n" + "=" * 70)
    print("生成可视化图片")
    print("=" * 70)

    objectives = results['objectives']
    ecr_array = results['ecr_array']
    j_min_array = results['j_min_array']
    pareto_solutions = results['pareto_solutions']

    # 创建4面板图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 图1: 部署方案（取ECR最高的解）
    ax1 = axes[0, 0]
    best_idx = np.argmax(ecr_array)
    best_sol = pareto_solutions[best_idx]
    J = results['J']
    N_bin = results['N_bin']
    polygons = results['polygons']
    task_points = results['task_points']

    # 绘制区域
    for poly in polygons:
        x, y = poly.exterior.xy
        ax1.fill(x, y, alpha=0.3, color='lightblue', edgecolor='blue', linewidth=1)

    # 绘制任务点
    task_x = [t.x for t in task_points]
    task_y = [t.y for t in task_points]
    ax1.scatter(task_x, task_y, c='gray', s=1, alpha=0.3)

    # 绘制雷达位置
    continuous = best_sol[:, :2].flatten()
    binary = best_sol[:, 2:2+N_bin]
    positions = decode_particle(continuous, binary, J, N_bin, polygons)
    pos_array = np.array(positions)
    ax1.scatter(pos_array[:, 0], pos_array[:, 1], c='red', s=100, marker='^',
               edgecolors='black', linewidth=1.5, zorder=5)
    for i, (x, y) in enumerate(positions):
        ax1.annotate(f'R{i+1}', (x, y), textcoords="offset points",
                    xytext=(5, 5), fontsize=8, fontweight='bold')
    ax1.set_xlabel('X (km)', fontsize=12)
    ax1.set_ylabel('Y (km)', fontsize=12)
    ax1.set_title('部署方案', fontsize=14)
    ax1.set_xlim(-10, 310)
    ax1.set_ylim(-10, 310)
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)

    # 图2: Pareto前沿
    ax2 = axes[0, 1]
    scatter = ax2.scatter(objectives[:, 0], objectives[:, 1],
                         c=np.arange(len(objectives)), cmap='viridis',
                         s=80, alpha=0.7, edgecolors='black', linewidth=0.5)
    ax2.set_xlabel('f1 = 1 - ECR', fontsize=12)
    ax2.set_ylabel('f2 = J_norm', fontsize=12)
    ax2.set_title(f'Pareto前沿 ({len(objectives)}个解)', fontsize=14)
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax2, label='解序号')

    # 图3: ECR热力图
    ax3 = axes[1, 0]
    # 创建ECR随位置变化的热力图
    grid_size = 10
    x_grid = np.linspace(0, 300, grid_size)
    y_grid = np.linspace(0, 300, grid_size)
    X, Y = np.meshgrid(x_grid, y_grid)

    # 使用最佳解计算每个点的ECR
    ecr_grid = np.zeros((grid_size, grid_size))
    for i in range(grid_size):
        for j in range(grid_size):
            target_pos = (X[i, j], Y[i, j])
            # 计算该点的联合探测概率
            joint_prob = 1.0
            for k in range(J):
                radar_pos = (pos_array[k, 0], pos_array[k, 1])
                dx = radar_pos[0] - target_pos[0]
                dy = radar_pos[1] - target_pos[1]
                d = np.sqrt(dx**2 + dy**2)
                if d < 1e-9:
                    P_detect = 1.0
                else:
                    d_m = d * 1000
                    G_linear = 10 ** (results['radar_configs'][0].G_t_dB / 10.0)
                    D0_linear = 10 ** (results['radar_configs'][0].D0_dB / 10.0)
                    P_t = results['radar_configs'][0].P_t
                    wavelength = results['radar_configs'][0].wavelength
                    sigma = results['radar_configs'][0].sigma
                    bandwidth = results['radar_configs'][0].bandwidth
                    k_B = 1.38e-23
                    T0 = 290.0
                    numerator = P_t * (G_linear ** 2) * (wavelength ** 2) * sigma
                    denominator = ((4 * np.pi) ** 3) * k_B * T0 * bandwidth * (d_m ** 4)
                    if denominator < 1e-30:
                        SNR = 1e10
                    else:
                        SNR = numerator / denominator
                    P_detect = np.exp(-D0_linear / (1.0 + SNR))
                    P_detect = np.clip(P_detect, 0.0, 1.0)
                joint_prob *= (1 - P_detect)
            joint_prob = 1 - joint_prob
            ecr_grid[i, j] = joint_prob

    im3 = ax3.contourf(X, Y, ecr_grid, levels=20, cmap='YlOrRd')
    ax3.scatter(pos_array[:, 0], pos_array[:, 1], c='blue', s=50, marker='^',
               edgecolors='black', linewidth=1, zorder=5)
    ax3.set_xlabel('X (km)', fontsize=12)
    ax3.set_ylabel('Y (km)', fontsize=12)
    ax3.set_title('ECR热力图', fontsize=14)
    ax3.set_aspect('equal')
    plt.colorbar(im3, ax=ax3, label='探测概率')

    # 图4: J_min热力图
    ax4 = axes[1, 1]
    j_grid = np.zeros((grid_size, grid_size))
    for i in range(grid_size):
        for j in range(grid_size):
            target_pos = (X[i, j], Y[i, j])
            total_j = 0.0
            for k in range(J):
                jammer_pos = (pos_array[k, 0], pos_array[k, 1])
                dx = jammer_pos[0] - target_pos[0]
                dy = jammer_pos[1] - target_pos[1]
                d = np.sqrt(dx**2 + dy**2)
                if d < 1e-9:
                    total_j += 1e10
                else:
                    d_m = d * 1000
                    G_jammer = 10 ** (results['radar_configs'][0].jammer_G_t_dB / 10.0)
                    J_power = results['radar_configs'][0].jammer_P_t * G_jammer / (4 * np.pi * (d_m ** 2))
                    total_j += J_power
            j_grid[i, j] = total_j

    im4 = ax4.contourf(X, Y, j_grid, levels=20, cmap='YlGnBu')
    ax4.scatter(pos_array[:, 0], pos_array[:, 1], c='red', s=50, marker='^',
               edgecolors='black', linewidth=1, zorder=5)
    ax4.set_xlabel('X (km)', fontsize=12)
    ax4.set_ylabel('Y (km)', fontsize=12)
    ax4.set_title('J_min热力图', fontsize=14)
    ax4.set_aspect('equal')
    plt.colorbar(im4, ax=ax4, label='干扰功率密度 (W/m²)')

    plt.tight_layout()
    save_path = os.path.join(PROJECT_ROOT, 'figures', 'paper_aligned_results.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"    综合结果图已保存: {save_path}")
    plt.close()

    # 单独保存Pareto前沿图
    fig2, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(objectives[:, 0], objectives[:, 1],
                        c=np.arange(len(objectives)), cmap='viridis',
                        s=100, alpha=0.7, edgecolors='black', linewidth=0.5)
    ax.set_xlabel('f1 = 1 - ECR', fontsize=14)
    ax.set_ylabel('f2 = J_norm', fontsize=14)
    ax.set_title(f'Pareto前沿 ({len(objectives)}个解)', fontsize=16)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='解序号')
    plt.tight_layout()
    save_path2 = os.path.join(PROJECT_ROOT, 'figures', 'paper_aligned_pareto.png')
    plt.savefig(save_path2, dpi=150, bbox_inches='tight')
    print(f"    Pareto前沿图已保存: {save_path2}")
    plt.close()

    # 相关性分析图
    if len(ecr_array) > 2:
        fig3, ax = plt.subplots(figsize=(8, 6))
        correlation = np.corrcoef(ecr_array, j_min_array)[0, 1]
        ax.scatter(ecr_array, j_min_array, c='purple', s=80, alpha=0.7)
        ax.set_xlabel('ECR', fontsize=14)
        ax.set_ylabel('J_min (W/m²)', fontsize=14)
        ax.set_title(f'ECR vs J_min (相关系数: {correlation:.3f})', fontsize=16)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        save_path3 = os.path.join(PROJECT_ROOT, 'figures', 'paper_aligned_correlation.png')
        plt.savefig(save_path3, dpi=150, bbox_inches='tight')
        print(f"    相关性图已保存: {save_path3}")
        plt.close()


def main():
    print("\n" + "#" * 70)
    print("# 基于参考论文参数的仿真实验")
    print("#" * 70)

    results = run_paper_experiment()

    if results is None:
        print("\n[错误] 实验失败")
        return

    # 可视化
    visualize_results(results)

    print("\n" + "#" * 70)
    print("# 实验完成")
    print("#" * 70)


if __name__ == "__main__":
    main()
