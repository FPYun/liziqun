from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def summarize_array(arr: np.ndarray) -> dict | float | int | str:
    if arr.shape == ():
        value = arr.item()
        if isinstance(value, (np.integer, int)):
            return int(value)
        if isinstance(value, (np.floating, float)):
            return float(value)
        return str(value)

    if arr.dtype.kind in "fiu":
        return {
            "n": int(arr.size),
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "mean": float(np.nanmean(arr)),
        }

    return {
        "n": int(arr.size),
        "dtype": str(arr.dtype),
    }


def summarize_file(path: Path) -> dict:
    with np.load(path) as data:
        return {key: summarize_array(data[key]) for key in data.files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="results/ablation_summary.json")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    summary = {}
    for path in sorted(results_dir.glob("ablation_*.npz")):
        key = path.stem.removeprefix("ablation_")
        summary[key] = summarize_file(path)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
