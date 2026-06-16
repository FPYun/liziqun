"""Generate a Chinese version of tradeoff_fixed for thesis formatting."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
THESIS_FIG = ROOT / "TongjiThesis-1.4.3" / "figures"


plt.rcParams.update(
    {
        "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
    }
)


SERIES = [
    {
        "nodes": 8,
        "n": 28,
        "corr": -0.988,
        "x": np.array(
            [
                0.010,
                0.025,
                0.028,
                0.031,
                0.034,
                0.036,
                0.042,
                0.048,
                0.052,
                0.061,
                0.080,
                0.120,
                0.135,
                0.142,
                0.148,
                0.151,
                0.190,
                0.196,
                0.199,
                0.204,
                0.208,
                0.211,
                0.214,
                0.217,
                0.220,
                0.222,
                0.225,
                0.228,
            ]
        ),
        "y": np.array(
            [
                0.0099,
                0.0091,
                0.00905,
                0.00880,
                0.00875,
                0.00870,
                0.00830,
                0.00825,
                0.00810,
                0.00802,
                0.00795,
                0.00705,
                0.00630,
                0.00570,
                0.00525,
                0.00505,
                0.00445,
                0.00362,
                0.00350,
                0.00342,
                0.00335,
                0.00325,
                0.00310,
                0.00302,
                0.00292,
                0.00284,
                0.00280,
                0.00276,
            ]
        ),
        "knee": 12,
    },
    {
        "nodes": 12,
        "n": 14,
        "corr": -0.970,
        "x": np.array([0.100, 0.135, 0.168, 0.205, 0.220, 0.245, 0.248, 0.252, 0.258, 0.262, 0.268, 0.276, 0.295, 0.309]),
        "y": np.array([0.0174, 0.0153, 0.0151, 0.01435, 0.01255, 0.01245, 0.01075, 0.01035, 0.01015, 0.01000, 0.00980, 0.00965, 0.00940, 0.00845]),
        "knee": 5,
    },
    {
        "nodes": 16,
        "n": 18,
        "corr": -0.954,
        "x": np.array([0.105, 0.120, 0.140, 0.235, 0.245, 0.265, 0.290, 0.315, 0.328, 0.358, 0.385, 0.392, 0.408, 0.455, 0.458, 0.474, 0.482, 0.495]),
        "y": np.array([0.0236, 0.0232, 0.0230, 0.0228, 0.0205, 0.0197, 0.0195, 0.0188, 0.0175, 0.0174, 0.0169, 0.0162, 0.0141, 0.0126, 0.0102, 0.0102, 0.0100, 0.00955]),
        "knee": 10,
    },
]


def main() -> None:
    THESIS_FIG.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.6), constrained_layout=True)
    cmap = plt.get_cmap("coolwarm")

    for ax, item in zip(axes, SERIES):
        x = item["x"]
        y = item["y"]
        colors = cmap(np.linspace(0.15, 0.85, len(x)))
        ax.scatter(x, y, s=22, c=colors, edgecolors="#777777", linewidths=0.35, alpha=0.9)
        knee = item["knee"]
        ax.scatter(
            [x[knee]],
            [y[knee]],
            marker="*",
            s=95,
            facecolor="#F2C94C",
            edgecolor="black",
            linewidth=0.9,
            zorder=4,
        )
        ax.set_title(f"J = {item['nodes']}（{item['n']}个解，r={item['corr']:.3f}）")
        ax.set_xlabel("有效覆盖率 ECR")
        ax.set_ylabel("最小等效干扰强度 Jmin")
        ax.grid(alpha=0.22)

    fig.suptitle("覆盖率-最小干扰强度 Pareto 前沿", fontsize=12)
    png_path = THESIS_FIG / "tradeoff_fixed.png"
    pdf_path = THESIS_FIG / "tradeoff_fixed.pdf"
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"Saved: {png_path}")
    print(f"Saved: {pdf_path}")


if __name__ == "__main__":
    main()
