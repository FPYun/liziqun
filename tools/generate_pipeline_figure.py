"""Generate Fig. 4.7 MOPSO-DT iteration pipeline."""

from __future__ import annotations

import os

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
ROOT_FIG_DIR = ROOT / "figures"
THESIS_FIG_DIR = ROOT / "TongjiThesis-1.4.3" / "figures"

FONT_PATHS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simsun.ttc",
]
FONT = FontProperties(fname=str(next((p for p in FONT_PATHS if p.exists()), FONT_PATHS[0])))


def add_box(ax, x, y, w, h, lines):
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.25,
        edgecolor="#0B1B4D",
        facecolor="#E8EEF2",
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h / 2,
        "\n".join(lines),
        ha="center",
        va="center",
        multialignment="center",
        fontsize=12.5,
        fontproperties=FONT,
        linespacing=1.0,
        color="#111111",
    )


def add_arrow(ax, start, end, connectionstyle="arc3"):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.25,
            color="#555555",
            shrinkA=0,
            shrinkB=0,
            connectionstyle=connectionstyle,
        )
    )


def main():
    ROOT_FIG_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_FIG_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9.2, 2.15))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 2.35)
    ax.axis("off")

    w, h = 1.55, 0.78
    y = 1.2
    xs = [0.15, 2.35, 4.55, 6.75, 8.95]
    labels = [
        ["初始化", "粒子"],
        ["更新", "混合变量"],
        ["映射到", "物理节点"],
        ["计算ECR", r"与$J_{\min}$"],
        ["更新", "档案"],
    ]

    for x, lines in zip(xs, labels):
        add_box(ax, x, y, w, h, lines)

    cy = y + h / 2
    for left in xs[:-1]:
        add_arrow(ax, (left + w + 0.08, cy), (left + 2.2 - 0.10, cy))

    # Feedback path stays clearly below all boxes and returns to the initializer.
    bottom_y = y - 0.26
    last_cx = xs[-1] + w / 2
    first_cx = xs[0] + w / 2
    ax.plot([last_cx, last_cx], [y, bottom_y], color="#555555", linewidth=1.25)
    ax.plot([last_cx, first_cx], [bottom_y, bottom_y], color="#555555", linewidth=1.25)
    add_arrow(ax, (first_cx, bottom_y), (first_cx, y - 0.04))

    ax.text(
        5.5,
        0.28,
        "重复执行，直到评价预算耗尽",
        ha="center",
        va="center",
        fontsize=11.5,
        fontproperties=FONT,
        color="#333333",
    )

    fig.savefig(ROOT_FIG_DIR / "fig_pipeline.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(ROOT_FIG_DIR / "fig_pipeline.svg", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(THESIS_FIG_DIR / "fig_pipeline.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
