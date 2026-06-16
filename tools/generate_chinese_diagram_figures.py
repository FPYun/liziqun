"""Generate Chinese-labeled explanatory figures for the thesis."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
ROOT_FIG_DIR = ROOT / "figures"
THESIS_FIG_DIR = ROOT / "TongjiThesis-1.4.3" / "figures"
THESIS_SOURCE_DIR = THESIS_FIG_DIR / "source"

FONT_PATHS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simsun.ttc",
]
FONT = FontProperties(fname=str(next((p for p in FONT_PATHS if p.exists()), FONT_PATHS[0])))


def setup_ax(figsize, xlim, ylim):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, lines, fc, ec, size=13, weight="normal", color="#1f2937"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.03,rounding_size=0.09",
        linewidth=1.35,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        "\n".join(lines),
        ha="center",
        va="center",
        multialignment="center",
        fontproperties=FONT,
        fontsize=size,
        fontweight=weight,
        linespacing=1.12,
        color=color,
    )


def arrow(ax, start, end, color="#4e5d6c", rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.35,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=4,
            shrinkB=4,
        )
    )


def save(fig, stem, source_svg=False):
    ROOT_FIG_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_FIG_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ROOT_FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(ROOT_FIG_DIR / f"{stem}.svg", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(THESIS_FIG_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.04)
    if source_svg:
        fig.savefig(THESIS_SOURCE_DIR / f"{stem}.svg", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def intro_research_framework():
    fig, ax = setup_ax((7.8, 3.9), (0, 10), (0, 5.1))
    box(ax, 0.35, 3.0, 1.8, 1.0, ["任务", "需求"], "#f3f6f8", "#4e5d6c", 14)
    box(ax, 2.75, 3.55, 1.8, 0.8, ["复杂", "区域"], "#eef5fb", "#4e5d6c", 14)
    box(ax, 2.75, 2.45, 1.8, 0.8, ["空地", "传播模型"], "#eef5fb", "#4e5d6c", 14)
    box(ax, 5.15, 3.05, 1.85, 1.0, ["MOPSO-DT", "搜索"], "#fff7ec", "#9b6a2f", 14)
    box(ax, 7.55, 3.55, 1.9, 0.8, ["有效覆盖率", "ECR"], "#f0f8ef", "#4e7d4a", 14)
    box(ax, 7.55, 2.45, 1.9, 0.8, ["最小压制", r"$J_{\min}$"], "#f0f8ef", "#4e7d4a", 14)
    box(ax, 3.95, 0.65, 2.5, 0.9, ["帕累托档案", "任务方案选择"], "#f7f2fa", "#725a7a", 14)

    arrow(ax, (2.15, 3.55), (2.75, 3.95))
    arrow(ax, (2.15, 3.45), (2.75, 2.85))
    arrow(ax, (4.55, 3.95), (5.15, 3.6))
    arrow(ax, (4.55, 2.85), (5.15, 3.35))
    arrow(ax, (7.0, 3.6), (7.55, 3.95))
    arrow(ax, (7.0, 3.35), (7.55, 2.85))
    arrow(ax, (8.5, 2.45), (5.95, 1.55))
    arrow(ax, (8.5, 3.55), (5.95, 1.55))
    save(fig, "intro_research_framework", source_svg=True)


def fig_inference():
    fig, ax = setup_ax((8.8, 4.9), (0, 10), (0, 6))
    ax.add_patch(FancyBboxPatch((0.25, 0.25), 9.5, 5.5, boxstyle="round,pad=0.02", fill=False, edgecolor="#cbd5e1", linewidth=1.4, linestyle=(0, (5, 4))))
    ax.text(5, 5.45, "候选部署方案的目标函数计算链路", ha="center", va="center", fontproperties=FONT, fontsize=17, fontweight="bold", color="#111827")

    box(ax, 4.0, 4.45, 2.0, 0.6, ["候选方案", "部署编码"], "#e0f2fe", "#0ea5e9", 14, "bold")
    box(ax, 4.0, 3.65, 2.0, 0.65, ["粒子解码", "得到物理位置"], "#dbeafe", "#3b82f6", 14, "bold")
    box(ax, 4.0, 2.75, 2.0, 0.65, ["传播模型", "A2G/G2G路径损耗"], "#fef3c7", "#f59e0b", 14, "bold")
    box(ax, 2.1, 1.7, 2.15, 0.7, ["ECR评价", "覆盖指标"], "#dcfce7", "#22c55e", 14, "bold")
    box(ax, 5.75, 1.7, 2.15, 0.7, [r"$J_{\min}$评价", "最弱点压制指标"], "#fee2e2", "#ef4444", 14, "bold")
    box(ax, 3.55, 0.55, 2.9, 0.65, ["目标向量", "多目标比较"], "#f3e8ff", "#a855f7", 14, "bold")
    box(ax, 7.0, 0.55, 2.1, 0.65, ["帕累托档案", "非支配解集"], "#ecfeff", "#06b6d4", 14, "bold")

    arrow(ax, (5, 4.45), (5, 4.3))
    arrow(ax, (5, 3.65), (5, 3.4))
    arrow(ax, (5, 2.75), (3.18, 2.4))
    arrow(ax, (5, 2.75), (6.82, 2.4))
    arrow(ax, (3.18, 1.7), (5, 1.2))
    arrow(ax, (6.82, 1.7), (5, 1.2))
    arrow(ax, (6.45, 0.88), (7.0, 0.88))
    save(fig, "fig_inference")


def fig_architecture():
    fig, ax = setup_ax((8.6, 3.7), (0, 10), (0, 4.4))
    ax.text(0.7, 3.65, "输入层", ha="center", va="center", fontproperties=FONT, fontsize=15, fontweight="bold", color="#0369a1")
    ax.text(0.7, 2.45, "预处理层", ha="center", va="center", fontproperties=FONT, fontsize=15, fontweight="bold", color="#1d4ed8")
    ax.text(0.7, 1.25, "优化与输出", ha="center", va="center", fontproperties=FONT, fontsize=15, fontweight="bold", color="#b45309")

    box(ax, 1.45, 3.25, 1.55, 0.72, ["部署区域", "复杂多边形"], "#e0f2fe", "#0ea5e9", 13)
    box(ax, 3.25, 3.25, 1.55, 0.72, ["雷达/干扰", "参数"], "#e0f2fe", "#0ea5e9", 13)
    box(ax, 5.05, 3.25, 1.55, 0.72, ["任务点", "均匀网格"], "#e0f2fe", "#0ea5e9", 13)
    box(ax, 2.05, 2.05, 2.0, 0.72, ["区域分解", "凸子区域编码"], "#dbeafe", "#3b82f6", 14)
    box(ax, 4.75, 2.05, 2.0, 0.72, ["坐标变换", "垂直交点法"], "#dbeafe", "#3b82f6", 14)
    box(ax, 2.0, 0.85, 2.1, 0.72, ["MOPSO-DT", "多目标搜索"], "#fef3c7", "#f59e0b", 14, "bold")
    box(ax, 4.45, 0.85, 1.75, 0.72, ["ECR评价", "覆盖率"], "#dcfce7", "#22c55e", 14)
    box(ax, 6.55, 0.85, 1.75, 0.72, [r"$J_{\min}$评价", "压制强度"], "#fee2e2", "#ef4444", 14)
    box(ax, 7.75, 2.05, 1.85, 0.72, ["帕累托前沿", "方案选择"], "#f3e8ff", "#a855f7", 14, "bold")

    arrow(ax, (2.22, 3.25), (2.85, 2.77))
    arrow(ax, (4.03, 3.25), (3.25, 2.77))
    arrow(ax, (5.82, 3.25), (5.75, 2.77))
    arrow(ax, (4.05, 2.41), (4.75, 2.41))
    arrow(ax, (3.05, 2.05), (3.05, 1.57))
    arrow(ax, (5.75, 2.05), (3.25, 1.57), rad=-0.12)
    arrow(ax, (4.1, 1.21), (4.45, 1.21))
    arrow(ax, (6.2, 1.21), (6.55, 1.21))
    arrow(ax, (7.43, 1.57), (8.45, 2.05))
    save(fig, "fig_architecture")


def main():
    intro_research_framework()
    fig_inference()
    fig_architecture()


if __name__ == "__main__":
    main()
