"""
Pareto 前沿增强可视化

功能：
1. Pareto 前沿散点图（带颜色梯度和关键点标注）
2. 6 个代表性解均匀采样部署地图
3. 内嵌汇总表
4. 收敛曲线

从 GitHub 版本 visualize_new_model.py / visualize_results.py 提取改进。
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib


def plot_pareto_front_enhanced(objectives, save_path=None, title="Pareto Front",
                                label_dict=None):
    """增强的 Pareto 前沿图（带拐点标注和颜色梯度）

    Args:
        objectives: (N, 2) 数组 [f1, f2]（最小化问题）
        save_path: 保存路径
        title: 图表标题
        label_dict: {'best_cov': str, 'best_int': str, 'knee': str} 自定义标注

    Returns:
        fig, ax
    """
    from src.benchmarks import get_extreme_points

    best_cov_idx, best_int_idx, knee_idx = get_extreme_points(objectives)

    fig, ax = plt.subplots(figsize=(10, 8))

    # 颜色梯度：从红（低覆盖）到绿（高覆盖）
    colors = plt.cm.RdYlGn(np.linspace(0.3, 1, len(objectives)))
    ax.scatter(objectives[:, 0], objectives[:, 1], c=colors,
               alpha=0.85, s=80, edgecolors='black', linewidth=0.5, zorder=3)

    # 标注极值点和拐点
    annotations = [
        (best_cov_idx, label_dict.get('best_cov', 'Best f1') if label_dict else 'Best f1',
         'darkred', (10, 20)),
        (best_int_idx, label_dict.get('best_int', 'Best f2') if label_dict else 'Best f2',
         'darkblue', (-50, -25)),
        (knee_idx, label_dict.get('knee', 'Knee (balance)') if label_dict else 'Knee',
         'darkgreen', (20, -20)),
    ]

    for idx, label, color, offset in annotations:
        ax.annotate(f'{label}\n({objectives[idx, 0]:.4f}, {objectives[idx, 1]:.4f})',
                    (objectives[idx, 0], objectives[idx, 1]),
                    xytext=offset, textcoords='offset points', fontsize=10,
                    arrowprops=dict(arrowstyle='->', color=color, lw=1.5),
                    color=color, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    ax.set_xlabel('f1 (minimize)', fontsize=13)
    ax.set_ylabel('f2 (minimize)', fontsize=13)
    ax.set_title(f'{title}\n{len(objectives)} non-dominated solutions', fontsize=14)
    ax.grid(True, alpha=0.3)

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    return fig, ax


def plot_representative_deployments(objectives, physics_list, save_path=None,
                                     n_show=6, region_size=500, radar_range=50,
                                     title="Representative Pareto Solutions"):
    """2×3 部署地图：沿 Pareto 前沿均匀选取 6 个代表性解

    Args:
        objectives: (N, 2) 数组
        physics_list: 物理坐标列表 [(J,2), ...]
        save_path: 保存路径
        n_show: 展示几个解
        region_size: 区域大小 (km)
        radar_range: 雷达探测半径 (km)
        title: 图表标题

    Returns:
        fig, axes
    """
    from src.benchmarks import sample_representative_solutions

    indices = sample_representative_solutions(objectives, n_show)

    n_cols = 3
    n_rows = (n_show + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 6 * n_rows))
    axes = axes.flatten() if n_show > 1 else [axes]

    for ax_idx, sol_idx in enumerate(indices):
        ax = axes[ax_idx]
        ax.set_xlim(0, region_size)
        ax.set_ylim(0, region_size)
        ax.set_aspect('equal')
        ax.set_facecolor('#f8f8f8')

        pos = physics_list[sol_idx]
        cov = objectives[sol_idx, 0]
        intr = objectives[sol_idx, 1]

        # 覆盖圆（淡色）
        for (px, py) in pos:
            circle = plt.Circle((px, py), radar_range, fill=True,
                                color='steelblue', alpha=0.08,
                                linewidth=0.3, edgecolor='steelblue')
            ax.add_patch(circle)

        # 雷达位置
        ax.scatter(pos[:, 0], pos[:, 1], c='red', s=50, zorder=5,
                   edgecolors='darkred', linewidth=0.5)

        ax.set_title(f'#{ax_idx+1}: f1={cov:.4f}  f2={intr:.4f}', fontsize=11)
        ax.grid(True, alpha=0.3)

    # 隐藏多余的子图
    for ax_idx in range(len(indices), len(axes)):
        axes[ax_idx].set_visible(False)

    plt.suptitle(title, fontsize=15, y=1.01)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    return fig, axes


def plot_convergence_curve(history, T_max, save_path=None,
                            title="Convergence Curve"):
    """绘制收敛曲线（档案大小随迭代变化）

    Args:
        history: archive_size 历史列表
        T_max: 最大迭代次数
        save_path: 保存路径
        title: 图表标题

    Returns:
        fig, ax
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    iterations = np.linspace(0, T_max, len(history))
    ax.plot(iterations, history, color='steelblue', linewidth=1.5)
    ax.fill_between(iterations, history, alpha=0.15, color='steelblue')
    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Archive Size', fontsize=12)
    ax.set_title(f'{title}\nFinal: {history[-1]} solutions', fontsize=13)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, T_max)

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    return fig, ax


def plot_comprehensive_pareto(objectives, physics_list=None, history=None,
                               T_max=None, save_path=None, title="MOPSO Results",
                               region_size=500, radar_range=50):
    """综合 2×3 布局：Pareto 前沿 + 收敛曲线 + 部署地图 + 汇总表

    Args:
        objectives: (N, 2) 数组
        physics_list: 物理坐标列表（可选）
        history: 收敛历史（可选）
        T_max: 最大迭代次数
        save_path: 保存路径
        title: 总标题
        region_size: 区域大小
        radar_range: 雷达探测半径

    Returns:
        fig
    """
    from src.benchmarks import get_extreme_points, sample_representative_solutions

    n_sols = len(objectives)
    fig = plt.figure(figsize=(22, 12))

    # (0,0): Pareto 前沿
    ax1 = fig.add_subplot(2, 3, 1)
    best_cov_idx, best_int_idx, knee_idx = get_extreme_points(objectives)
    colors = plt.cm.RdYlGn(np.linspace(0.3, 1, n_sols))
    ax1.scatter(objectives[:, 0], objectives[:, 1], c=colors,
                alpha=0.85, s=60, edgecolors='black', linewidth=0.5, zorder=3)

    for idx, label, color, offset in [
        (best_cov_idx, 'Best f1', 'darkred', (10, 20)),
        (best_int_idx, 'Best f2', 'darkblue', (-50, -25)),
        (knee_idx, 'Knee', 'darkgreen', (20, -20)),
    ]:
        ax1.annotate(f'{label}\n({objectives[idx, 0]:.4f}, {objectives[idx, 1]:.4f})',
                     (objectives[idx, 0], objectives[idx, 1]),
                     xytext=offset, textcoords='offset points', fontsize=9,
                     arrowprops=dict(arrowstyle='->', color=color, lw=1.2),
                     color=color, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
    ax1.set_xlabel('f1 (minimize)', fontsize=12)
    ax1.set_ylabel('f2 (minimize)', fontsize=12)
    ax1.set_title(f'Pareto Front ({n_sols} solutions)', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # (0,1): 收敛曲线
    ax2 = fig.add_subplot(2, 3, 2)
    if history is not None and T_max is not None:
        its = np.linspace(0, T_max, len(history))
        ax2.plot(its, history, color='steelblue', linewidth=1.5)
        ax2.fill_between(its, history, alpha=0.15, color='steelblue')
    ax2.set_xlabel('Iteration', fontsize=12)
    ax2.set_ylabel('Archive Size', fontsize=12)
    ax2.set_title('Convergence', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # (0,2): f1/f2 直方图
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.hist(objectives[:, 0], bins=15, alpha=0.7, label='f1', color='steelblue')
    ax3_2 = ax3.twinx()
    ax3_2.hist(objectives[:, 1], bins=15, alpha=0.5, label='f2', color='red')
    ax3.set_xlabel('Objective Value', fontsize=12)
    ax3.set_ylabel('f1 Count', color='steelblue', fontsize=12)
    ax3_2.set_ylabel('f2 Count', color='red', fontsize=12)
    ax3.set_title('Objective Value Distribution', fontsize=13, fontweight='bold')
    ax3.legend(loc='upper left')
    ax3_2.legend(loc='upper right')

    # (1,0): 最佳 f1 部署
    ax4 = fig.add_subplot(2, 3, 4)
    if physics_list is not None:
        phys_best = physics_list[best_cov_idx]
        ax4.set_xlim(0, region_size)
        ax4.set_ylim(0, region_size)
        ax4.set_aspect('equal')
        for (px, py) in phys_best:
            circle = plt.Circle((px, py), radar_range, fill=False, color='gray',
                                alpha=0.1, linewidth=0.15)
            ax4.add_patch(circle)
        ax4.scatter(phys_best[:, 0], phys_best[:, 1], c='red', s=8, zorder=3,
                    edgecolors='darkred', linewidth=0.2)
    ax4.set_title(f'Best f1: {objectives[best_cov_idx, 0]:.4f}', fontsize=12, fontweight='bold')
    ax4.set_xlabel('X (km)', fontsize=11)
    ax4.set_ylabel('Y (km)', fontsize=11)
    ax4.grid(True, alpha=0.3)

    # (1,1): 拐点部署
    ax5 = fig.add_subplot(2, 3, 5)
    if physics_list is not None:
        phys_knee = physics_list[knee_idx]
        ax5.set_xlim(0, region_size)
        ax5.set_ylim(0, region_size)
        ax5.set_aspect('equal')
        for (px, py) in phys_knee:
            circle = plt.Circle((px, py), radar_range, fill=False, color='gray',
                                alpha=0.1, linewidth=0.15)
            ax5.add_patch(circle)
        ax5.scatter(phys_knee[:, 0], phys_knee[:, 1], c='green', s=8, zorder=3,
                    edgecolors='darkgreen', linewidth=0.2)
    ax5.set_title(f'Knee: f1={objectives[knee_idx, 0]:.4f}, f2={objectives[knee_idx, 1]:.4f}',
                  fontsize=12, fontweight='bold')
    ax5.set_xlabel('X (km)', fontsize=11)
    ax5.set_ylabel('Y (km)', fontsize=11)
    ax5.grid(True, alpha=0.3)

    # (1,2): 汇总表
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.axis('off')
    f1_min, f1_max = objectives[:, 0].min(), objectives[:, 0].max()
    f2_min, f2_max = objectives[:, 1].min(), objectives[:, 1].max()
    f1_mean, f2_mean = objectives[:, 0].mean(), objectives[:, 1].mean()

    table_data = [
        ['Metric', 'Value'],
        ['Solutions', str(n_sols)],
        ['f1 Range', f'[{f1_min:.4f}, {f1_max:.4f}]'],
        ['f1 Mean', f'{f1_mean:.4f}'],
        ['f2 Range', f'[{f2_min:.4f}, {f2_max:.4f}]'],
        ['f2 Mean', f'{f2_mean:.4f}'],
        ['Knee f1', f'{objectives[knee_idx, 0]:.4f}'],
        ['Knee f2', f'{objectives[knee_idx, 1]:.4f}'],
    ]
    table = ax6.table(cellText=table_data, cellLoc='center', loc='center',
                       colWidths=[0.35, 0.65])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.6)
    for i in range(2):
        table[(0, i)].set_facecolor('#333333')
        table[(0, i)].set_text_props(color='white', fontweight='bold', fontsize=11)
    for r in range(1, len(table_data)):
        table[(r, 0)].set_facecolor('#e0e0e0')
        table[(r, 0)].set_text_props(fontweight='bold')
    # 高亮拐点行
    table[(len(table_data) - 2, 0)].set_facecolor('#a5d6a7')
    table[(len(table_data) - 1, 0)].set_facecolor('#a5d6a7')
    ax6.set_title('Summary', fontsize=13, fontweight='bold', y=0.98)

    plt.suptitle(title, fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

    return fig
