"""Generate Fig. 4.7 MOPSO-DT iteration pipeline."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
ROOT_FIG_DIR = ROOT / "figures"
THESIS_FIG_DIR = ROOT / "TongjiThesis-1.4.3" / "figures"


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
        fontsize=10.5,
        family="Times New Roman",
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

    fig, ax = plt.subplots(figsize=(8.4, 2.1))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.35)
    ax.axis("off")

    w, h = 1.45, 0.78
    y = 1.2
    xs = [0.15, 2.15, 4.15, 6.15, 8.15]
    labels = [
        ["Initialize", "particles"],
        ["Update", "continuous", "+ binary"],
        ["Map to", "physical", "nodes"],
        ["Evaluate", "ECR", "/ Jmin"],
        ["Update", "archive"],
    ]

    for x, lines in zip(xs, labels):
        add_box(ax, x, y, w, h, lines)

    cy = y + h / 2
    for left in xs[:-1]:
        add_arrow(ax, (left + w + 0.08, cy), (left + 2.0 - 0.10, cy))

    # Feedback path stays clearly below all boxes and returns to the initializer.
    bottom_y = y - 0.26
    last_cx = xs[-1] + w / 2
    first_cx = xs[0] + w / 2
    ax.plot([last_cx, last_cx], [y, bottom_y], color="#555555", linewidth=1.25)
    ax.plot([last_cx, first_cx], [bottom_y, bottom_y], color="#555555", linewidth=1.25)
    add_arrow(ax, (first_cx, bottom_y), (first_cx, y - 0.04))

    ax.text(
        5,
        0.28,
        "repeat until evaluation budget is exhausted",
        ha="center",
        va="center",
        fontsize=9.5,
        family="Times New Roman",
        color="#333333",
    )

    fig.savefig(ROOT_FIG_DIR / "fig_pipeline.png", dpi=300, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(ROOT_FIG_DIR / "fig_pipeline.svg", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(THESIS_FIG_DIR / "fig_pipeline.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
