"""Generate Chinese-labeled process figures used in Chapter 4."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, Polygon


ROOT = Path(__file__).resolve().parents[1]
THESIS_FIG_DIR = ROOT / "TongjiThesis-1.4.3" / "figures"
THESIS_SOURCE_DIR = THESIS_FIG_DIR / "source"

FONT_PATHS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simsun.ttc",
]
FONT = FontProperties(fname=str(next((p for p in FONT_PATHS if p.exists()), FONT_PATHS[0])))

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["svg.fonttype"] = "path"


def l_shape(x0: float, y0: float, w: float, h: float) -> list[tuple[float, float]]:
    return [
        (x0, y0),
        (x0 + w, y0),
        (x0 + w, y0 + h),
        (x0 + 0.62 * w, y0 + h),
        (x0 + 0.62 * w, y0 + 0.48 * h),
        (x0, y0 + 0.48 * h),
    ]


def panel_label(ax, x: float, y: float, marker: str, title: str) -> None:
    ax.text(x, y, marker, ha="left", va="center", fontsize=8, fontweight="bold")
    ax.text(
        x + 0.48,
        y,
        title,
        ha="center",
        va="center",
        fontproperties=FONT,
        fontsize=10,
    )


def save(fig, name: str) -> None:
    fig.savefig(THESIS_FIG_DIR / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(THESIS_SOURCE_DIR / f"{name}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def coordinate_transform_pipeline() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(5.8, 1.9))

    titles = ["区域编码", "归一化搜索", "物理部署"]
    markers = ["a", "b", "c"]

    for idx, ax in enumerate(axes):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        panel_label(ax, 0.02, 0.95, markers[idx], titles[idx])

    axes[0].add_patch(
        Polygon(l_shape(0.08, 0.08, 0.82, 0.68), closed=True, facecolor="#e9f2fa", edgecolor="#2f5c8a", linewidth=1.2)
    )
    axes[0].plot([0.58, 0.58], [0.08, 0.405], "--", color="#c95f35", linewidth=1.0)
    axes[0].text(0.30, 0.22, "00", ha="center", va="center", fontsize=8)
    axes[0].text(0.72, 0.58, "01", ha="center", va="center", fontsize=8)

    axes[1].add_patch(Polygon([(0.12, 0.08), (0.88, 0.08), (0.88, 0.84), (0.12, 0.84)], closed=True, fill=False, edgecolor="#4e5d6c", linewidth=1.2))
    axes[1].scatter([0.31, 0.66, 0.47], [0.58, 0.28, 0.41], s=28, color="#c95f35", zorder=3)

    axes[2].add_patch(
        Polygon(l_shape(0.08, 0.08, 0.82, 0.68), closed=True, facecolor="#e9f2fa", edgecolor="#2f5c8a", linewidth=1.2)
    )
    axes[2].scatter([0.25, 0.76, 0.43], [0.30, 0.53, 0.36], marker="^", s=52, color="#c95f35", edgecolor="white", linewidth=0.5)

    plt.subplots_adjust(left=0.015, right=0.985, top=0.93, bottom=0.05, wspace=0.18)
    save(fig, "coordinate_transform_pipeline")


def decomposition_pipeline() -> None:
    fig, axes = plt.subplots(1, 4, figsize=(5.95, 1.25))
    titles = ["原始区域", "切割线", "凸子区域", "二进制编码"]
    markers = ["a", "b", "c", "d"]

    for idx, ax in enumerate(axes):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        panel_label(ax, 0.01, 0.93, markers[idx], titles[idx])
        ax.add_patch(
            Polygon(l_shape(0.08, 0.08, 0.84, 0.68), closed=True, facecolor="#eef5fb", edgecolor="#2f5c8a", linewidth=1.1)
        )

    axes[1].plot([0.60, 0.60], [0.08, 0.40], "--", color="#c95f35", linewidth=1.0)

    axes[2].add_patch(Polygon([(0.08, 0.08), (0.60, 0.08), (0.60, 0.40), (0.08, 0.40)], closed=True, facecolor="#bfd8ee", edgecolor="#2f5c8a", linewidth=1.0))
    axes[2].add_patch(Polygon([(0.60, 0.08), (0.92, 0.08), (0.92, 0.76), (0.60, 0.76)], closed=True, facecolor="#ddeccb", edgecolor="#2f5c8a", linewidth=1.0))

    axes[3].text(0.34, 0.25, "编码0", ha="center", va="center", fontproperties=FONT, fontsize=8)
    axes[3].text(0.74, 0.50, "编码1", ha="center", va="center", fontproperties=FONT, fontsize=8)

    plt.subplots_adjust(left=0.012, right=0.988, top=0.92, bottom=0.05, wspace=0.16)
    save(fig, "decomposition_pipeline")


def decomposition_variety() -> None:
    fig, axes = plt.subplots(4, 2, figsize=(3.8, 4.9))
    row_labels = ["L形", "带空洞", "不连通", "锯齿形"]
    col_labels = ["原始区域", "分解结果"]

    for col, title in enumerate(col_labels):
        axes[0, col].set_title(title, fontproperties=FONT, fontsize=10, pad=4)

    for row in range(4):
        for col in range(2):
            ax = axes[row, col]
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_aspect("equal")
            ax.axis("off")
            if col == 0:
                ax.text(-0.12, 0.5, row_labels[row], rotation=90, ha="center", va="center", fontproperties=FONT, fontsize=9)

    shapes = [
        l_shape(0.14, 0.16, 0.72, 0.68),
        [(0.12, 0.14), (0.88, 0.14), (0.88, 0.84), (0.12, 0.84)],
        [(0.15, 0.18), (0.42, 0.18), (0.42, 0.55), (0.15, 0.55)],
        [(0.12, 0.15), (0.84, 0.15), (0.72, 0.30), (0.84, 0.45), (0.72, 0.60), (0.84, 0.80), (0.12, 0.80)],
    ]

    for row, pts in enumerate(shapes):
        axes[row, 0].add_patch(Polygon(pts, closed=True, facecolor="#eef0ff", edgecolor="navy", linewidth=1.0))

    axes[1, 0].add_patch(Polygon([(0.43, 0.38), (0.57, 0.38), (0.57, 0.60), (0.43, 0.60)], closed=True, fill=False, edgecolor="#c95f35", linestyle="--", linewidth=0.9))

    # L shape decomposition.
    axes[0, 1].add_patch(Polygon([(0.12, 0.16), (0.56, 0.16), (0.56, 0.48), (0.12, 0.48)], closed=True, facecolor="#d8ecec", edgecolor="navy", linewidth=1.0))
    axes[0, 1].add_patch(Polygon([(0.56, 0.16), (0.86, 0.16), (0.86, 0.84), (0.56, 0.84)], closed=True, facecolor="#c8ffd2", edgecolor="navy", linewidth=1.0))
    axes[0, 1].plot([0.56, 0.56], [0.16, 0.48], "--", color="#c95f35", linewidth=0.8)
    axes[0, 1].text(0.34, 0.32, "0", ha="center", va="center", fontsize=8)
    axes[0, 1].text(0.71, 0.53, "1", ha="center", va="center", fontsize=8)

    # Hole decomposition.
    axes[1, 1].add_patch(Polygon([(0.10, 0.14), (0.46, 0.14), (0.46, 0.84), (0.10, 0.84)], closed=True, facecolor="#d8ecec", edgecolor="navy", linewidth=1.0))
    axes[1, 1].add_patch(Polygon([(0.46, 0.14), (0.86, 0.14), (0.86, 0.84), (0.62, 0.84), (0.62, 0.36), (0.46, 0.36)], closed=True, facecolor="#c8ffd2", edgecolor="navy", linewidth=1.0))
    axes[1, 1].add_patch(Polygon([(0.46, 0.58), (0.62, 0.58), (0.62, 0.84), (0.46, 0.84)], closed=True, facecolor="#fff7cc", edgecolor="navy", linewidth=1.0))
    axes[1, 1].add_patch(Polygon([(0.46, 0.14), (0.62, 0.14), (0.62, 0.36), (0.46, 0.36)], closed=True, facecolor="#f9d6d5", edgecolor="navy", linewidth=1.0))
    axes[1, 1].plot([0.46, 0.46], [0.14, 0.84], "--", color="#c95f35", linewidth=0.8)
    axes[1, 1].plot([0.62, 0.62], [0.14, 0.84], "--", color="#c95f35", linewidth=0.8)
    axes[1, 1].text(0.28, 0.46, "0", ha="center", va="center", fontsize=8)
    axes[1, 1].text(0.73, 0.46, "1", ha="center", va="center", fontsize=8)
    axes[1, 1].text(0.54, 0.70, "2", ha="center", va="center", fontsize=8)
    axes[1, 1].text(0.54, 0.25, "3", ha="center", va="center", fontsize=8)

    # Disconnected decomposition.
    axes[2, 1].add_patch(Polygon([(0.15, 0.20), (0.43, 0.20), (0.43, 0.52), (0.15, 0.52)], closed=True, facecolor="#d8ecec", edgecolor="navy", linewidth=1.0))
    axes[2, 1].add_patch(Polygon([(0.63, 0.54), (0.88, 0.54), (0.88, 0.85), (0.63, 0.85)], closed=True, facecolor="#c8ffd2", edgecolor="navy", linewidth=1.0))
    axes[2, 1].text(0.29, 0.36, "0", ha="center", va="center", fontsize=8)
    axes[2, 1].text(0.76, 0.70, "1", ha="center", va="center", fontsize=8)

    # Saw-tooth decomposition.
    axes[3, 1].add_patch(Polygon([(0.12, 0.15), (0.58, 0.15), (0.58, 0.80), (0.12, 0.80)], closed=True, facecolor="#d8ecec", edgecolor="navy", linewidth=1.0))
    axes[3, 1].add_patch(Polygon([(0.58, 0.15), (0.84, 0.15), (0.72, 0.30), (0.84, 0.45), (0.72, 0.60), (0.84, 0.80), (0.58, 0.80)], closed=True, facecolor="#c8ffd2", edgecolor="navy", linewidth=1.0))
    axes[3, 1].plot([0.58, 0.58], [0.15, 0.80], "--", color="#c95f35", linewidth=0.8)
    axes[3, 1].text(0.36, 0.46, "0", ha="center", va="center", fontsize=8)
    axes[3, 1].text(0.70, 0.46, "1", ha="center", va="center", fontsize=8)

    plt.subplots_adjust(left=0.12, right=0.98, top=0.94, bottom=0.03, hspace=0.30, wspace=0.12)
    save(fig, "decomposition_variety")


def coordinate_transform_overview() -> None:
    fig, ax = plt.subplots(figsize=(6.0, 2.45))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    ax.text(0.18, 3.72, "a", fontsize=9, fontweight="bold")
    ax.text(1.8, 3.72, "单位搜索空间", fontproperties=FONT, fontsize=12, ha="center")
    ax.text(6.45, 3.72, "b", fontsize=9, fontweight="bold")
    ax.text(8.05, 3.72, "凸物理单元", fontproperties=FONT, fontsize=12, ha="center")

    ax.plot([0.55, 0.55], [0.5, 3.2], color="#174a6a", linewidth=1.4)
    ax.plot([0.55, 3.25], [0.5, 0.5], color="#174a6a", linewidth=1.4)
    ax.add_patch(Polygon([(0.70, 0.65), (3.0, 0.65), (3.0, 3.05), (0.70, 3.05)], closed=True, fill=False, edgecolor="#174a6a", linewidth=1.2))
    for x in [1.28, 1.86, 2.44]:
        ax.plot([x, x], [0.65, 3.05], color="#a9b8b2", linewidth=0.55)
    for y in [1.25, 1.85, 2.45]:
        ax.plot([0.70, 3.0], [y, y], color="#a9b8b2", linewidth=0.55)
    points = [(1.12, 1.15), (1.55, 2.35), (2.62, 1.65), (2.88, 2.70)]
    ax.scatter([p[0] for p in points], [p[1] for p in points], s=30, color="#b65d31", zorder=3)
    ax.text(0.49, 3.05, "1", fontsize=8)
    ax.text(0.48, 0.42, "0", fontsize=8)
    ax.text(3.05, 0.40, r"$\hat{x}$", fontsize=9)
    ax.text(0.45, 3.27, r"$\hat{y}$", fontsize=9)
    ax.text(1.85, 0.38, "归一化坐标\n$[0,1]^2$ 内", fontproperties=FONT, fontsize=8, ha="center", va="top", linespacing=1.15)

    cell = [(6.9, 0.85), (9.45, 1.10), (8.85, 3.20), (7.25, 3.00)]
    ax.add_patch(Polygon(cell, closed=True, facecolor="#d9e9e1", edgecolor="#174a6a", linewidth=1.4))
    ax.scatter([7.25, 7.95, 8.75, 8.60], [1.35, 2.20, 1.80, 2.75], marker="^", s=54, color="#b65d31", edgecolor="white", linewidth=0.5, zorder=3)
    ax.text(8.15, 0.62, "所有映射点\n均保持可行", fontproperties=FONT, fontsize=8, ha="center", va="top", color="#174a6a", linespacing=1.15)

    ax.add_patch(FancyArrowPatch((4.05, 2.0), (5.85, 2.0), arrowstyle="-|>", mutation_scale=16, linewidth=1.2, color="#174a6a"))
    ax.text(4.95, 2.25, "单元专属\n坐标映射", fontproperties=FONT, fontsize=9, ha="center", linespacing=1.15)
    for start, end in zip(points, [(7.25, 1.35), (7.95, 2.20), (8.75, 1.80), (8.60, 2.75)]):
        ax.plot([start[0] + 0.15, end[0] - 0.18], [start[1], end[1]], "--", color="#a9b8b2", linewidth=0.7, alpha=0.8)

    save(fig, "coordinate_transform_overview")


def coordinate_transform_detail() -> None:
    fig, ax = plt.subplots(figsize=(6.1, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    poly = [(0.8, 1.25), (9.0, 1.9), (7.7, 4.95), (2.2, 4.25)]
    ax.add_patch(Polygon(poly, closed=True, facecolor="#d6e7df", edgecolor="#174a6a", linewidth=1.6))
    for x in [2.2, 4.4, 6.6, 8.2]:
        ax.plot([x, x], [1.0, 5.2], color="#9fb4aa", linewidth=0.6, alpha=0.8)
    for y in [2.0, 3.1, 4.2]:
        ax.plot([0.55, 9.45], [y, y], color="#9fb4aa", linewidth=0.6, alpha=0.8)

    scan_x, ymin, ymax, ystar = 6.15, 2.05, 4.55, 3.10
    ax.plot([scan_x, scan_x], [1.0, 5.2], "--", color="#c95f35", linewidth=1.0)
    ax.plot([scan_x, scan_x], [ymin, ymax], color="#2f7d45", linewidth=3.0)
    ax.scatter([scan_x, scan_x], [ymin, ymax], color="#174a6a", s=28, zorder=5)
    ax.scatter([scan_x], [ystar], marker="*", s=320, color="#d8891d", edgecolor="white", linewidth=1.0, zorder=6)

    ax.text(0.75, 5.36, "垂直交点坐标变换", fontproperties=FONT, fontsize=13, fontweight="bold", color="#111827")
    ax.text(0.75, 5.10, r"只在选定 $\hat{x}$ 截得的有效区间内采样", fontproperties=FONT, fontsize=9.5, color="#174a6a")
    ax.text(scan_x - 0.92, ymax + 0.16, r"$y_{\max}(\hat{x})$", fontsize=9.5, color="#174a6a")
    ax.text(scan_x + 0.12, ymin - 0.34, r"$y_{\min}(\hat{x})$", fontsize=9.5, color="#174a6a")
    ax.text(scan_x + 0.38, ystar - 0.50, r"$y=y_{\min}+\hat{y}(y_{\max}-y_{\min})$", fontsize=9.5, color="#174a6a")

    def callout(text: str, xy: tuple[float, float], xytext: tuple[float, float], size: int = 10) -> None:
        ax.annotate(
            text,
            xy=xy,
            xytext=xytext,
            ha="center",
            va="center",
            fontproperties=FONT,
            fontsize=size,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#8aa19a", linewidth=0.8),
            arrowprops=dict(arrowstyle="-|>", color="#174a6a", linewidth=1.1),
        )

    callout(r"$\hat{x}$ 确定扫描线", (scan_x, ymax), (8.10, 5.35), 10.5)
    callout(r"$\hat{y}$ 在有效区间内插值", (scan_x, ystar), (8.72, 3.78), 10.5)
    callout("当前扫描线\n有效 $y$ 范围", (scan_x, ymin), (1.45, 0.86), 9.5)

    save(fig, "coordinate_transform_detail")


def main() -> None:
    THESIS_FIG_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    coordinate_transform_pipeline()
    decomposition_pipeline()
    decomposition_variety()
    coordinate_transform_overview()
    coordinate_transform_detail()


if __name__ == "__main__":
    main()
