# Results Directory

This directory is the canonical intake location for structured experiment outputs used by ARIS.

## Expected files

- `quick_compare_results.json`
- `tune_results.json`
- `paper_aligned_results.json`
- `challenging_scene_results.json`
- `algorithm_comparison.json`
- `boundary_analysis.json`
- `ablation_*.npz`
- `ablation_summary.json`

## Source policy

- Files may be generated directly by experiment scripts or copied here from `figures/` by `tools/sync_results.ps1`.
- Only files in this directory should be treated as the final evidence source for `analyze-results`, `experiment-audit`, and `result-to-claim`.
- Plots in `figures/` remain useful, but they are supporting artifacts rather than the primary structured evidence source.

## Metric policy

- Keep raw physical metrics clearly separated from normalized optimization objectives.
- If a field stores normalized `f2`, do not label it as raw physical `J_min`.
