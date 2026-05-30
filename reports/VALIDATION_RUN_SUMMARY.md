# Validation Run Summary

Date: 2026-05-27

Purpose: learn the current `liziqun` project, rerun validation commands, regenerate comparison figures, and compile the current thesis container without modifying thesis prose.

Current thesis note: after the later official-template migration, the active thesis source is `TongjiThesis-1.4.3/`. The 2026-05-27 validation rows below are historical evidence from the earlier `TongjiThesis-1.4.0/` container. The current `TongjiThesis-1.4.3/main.pdf` has since been compiled successfully after the figure and format refinements.

## 1. Backup

Before running validation, the project was copied into:

```text
_backup_snapshot_20260527_081434
```

Backup content:

- Files: 137
- Bytes: 16,217,887
- Excluded: `.git`, existing `_backup_snapshot_*`

The backup sits inside the project root and is ignored by `.gitignore`.

## 2. Command Results

| Step | Command | Status | Notes |
|---|---|---|---|
| Tests | `E:\Anaconda\python.exe -m pytest tests -v --tb=short` | Passed | 47 passed, 6 warnings, 40.5 s pytest time. |
| Quick compare | `E:\Anaconda\python.exe experiments/quick_compare.py` | Passed after UTF-8 rerun | Initial run hit GBK path print error; rerun with `PYTHONIOENCODING=utf-8` passed. |
| Tune MOPSO | `E:\Anaconda\python.exe experiments/tune_mopso.py` | Result file completed; wrapper timed out | Full log shows completion and `figures/tune_results.json` was written; outer capture reached timeout before clean return. |
| Paper-aligned | `E:\Anaconda\python.exe experiments/experiment_paper_aligned.py` | Passed | Completed in about 335 s. |
| Challenging | `E:\Anaconda\python.exe experiments/experiment_challenging.py` | Passed | Completed in about 66 s. |
| Algorithm comparison | `E:\Anaconda\python.exe experiments/compare_algorithms.py` | Passed | Completed in about 1143 s; refreshed `results/algorithm_comparison.json`. |
| Boundary analysis | `E:\Anaconda\python.exe experiments/boundary_analysis.py` | Result file completed; wrapper timed out | `results/boundary_analysis.json` updated with 12 runs and 4 method summaries; stdout log was not captured. |
| Generate figures | `E:\Anaconda\python.exe tools/generate_comparison_figures.py` | Passed | Refreshed five PDF figures under `TongjiThesis-1.4.0/figures/`. |
| Compile thesis | `xelatex -> biber -> xelatex -> xelatex` | Passed | Generated `TongjiThesis-1.4.0/main.pdf`, 54 pages, size 3,420,195 bytes. |

Validation logs are under:

```text
reports/validation_logs/20260527_081434/
```

This directory is ignored by `.gitignore`.

## 3. Test Warnings

The test suite passed, but reported warnings:

- `pytest.mark.slow` is not registered.
- Several functions in `tests/test_mopso.py` return values instead of using only assertions.

These warnings do not fail validation but should be cleaned up later if test hygiene matters.

## 4. Key Experiment Results

### Quick Compare

The UTF-8 rerun completed. In this run:

- Baseline Pareto solutions: 12
- Improved Pareto solutions: 6
- Runtime improved by about 27.7%
- Hypervolume improved by about 4.9%
- Minimum `J_min` improved by about 27.4%

Interpretation: this run supports that the improved configuration can be faster and slightly improve HV, but it does not support a stable claim that Pareto solution count always increases.

### Tune MOPSO

The completed log and refreshed JSON indicate the best combination in this run:

```text
N_P = 50
T_max = 100
c_1 = 2.0
c_2 = 2.0
w_strategy = legacy
p_m_base = 0.0
select_gb = crowding
```

Metrics:

- HV: about 0.05245
- Pareto solutions: about 12.5
- Runtime: about 32.7 s
- ECR range: 0.1311--0.5733
- `J_min` normalized range: 0.04136--0.08314

The refreshed `figures/tune_results.json` was copied to `results/tune_results.json`.

### Paper-Aligned Scenario

This run completed with:

- Pareto solutions: 7
- ECR range: 0.7800--0.8500
- `J_min` range: `3.712057e-06`--`6.019032e-06`
- ECR--`J_min` correlation: about -0.9231
- Figures refreshed in `figures/`: `paper_aligned_results.png`, `paper_aligned_pareto.png`, `paper_aligned_correlation.png`

### Challenging Scenario

This run completed with:

- Pareto solutions: 10
- ECR range: 0.0311--0.2222
- `J_min` range: 0.00369132--0.00981975
- Correlation: about -0.968
- Figure refreshed: `figures/13_challenging_scene.png`

### Algorithm Comparison

`results/algorithm_comparison.json` was refreshed. Summary:

- MOEA/D has the highest mean HV: about 0.03481.
- SPEA2 has the lowest mean Spacing: about 0.00171.
- Ours has mean HV about 0.03081 and mean runtime about 58.27 s.
- Ours is faster than most evolutionary baselines in this run, but not best in HV, spacing, or maximum ECR.

### Boundary Analysis

`results/boundary_analysis.json` was refreshed. Summary:

- `ours_transform` boundary ECR mean: 0.15625.
- `direct_physical` boundary ECR mean: 0.15625.
- `mopso_legacy` boundary ECR mean: 0.11458.
- `nsga2` boundary ECR mean: 0.07639.
- NSGA-II has the highest overall ECR mean and highest HV in this boundary result.

Interpretation: coordinate transform supports a boundary-coverage improvement statement, but not a broad claim that it dominates all methods on all metrics.

## 5. Figure Generation

The following thesis PDF figures were regenerated successfully:

- `TongjiThesis-1.4.0/figures/algorithm_pareto_overlay.pdf`
- `TongjiThesis-1.4.0/figures/algorithm_metrics_bars.pdf`
- `TongjiThesis-1.4.0/figures/runtime_quality_tradeoff.pdf`
- `TongjiThesis-1.4.0/figures/knee_deployment_comparison.pdf`
- `TongjiThesis-1.4.0/figures/boundary_coverage_map.pdf`

All five exist after generation.

## 6. Compile Validation

The current thesis container compiled successfully:

- PDF: `TongjiThesis-1.4.0/main.pdf`
- Size: 3,420,195 bytes
- Final log checks:
  - undefined references: 0
  - undefined citations: 0
  - `Please rerun LaTeX`: 0
  - Biber rerun warning: 0
  - LaTeX Error: 0
  - biblatex warning: 0

## 7. Important Evidence Implications

- The current project is functional enough to run tests, major experiments, figure generation, and full thesis compilation.
- The current experimental evidence does not support overclaiming that MOPSO-DT is universally best.
- The boundary transform has evidence for improving boundary coverage relative to some baselines, but not for eliminating boundary effects.
- The parameter-tuning result from this validation conflicts with older wording that preferred `standard + crowding + p_m=0.01`.
- Existing thesis prose was not modified in this task.

## 8. Files Added By This Task

- `docs/PROJECT_SYSTEM_EXPLANATION.md`
- `docs/THESIS_EVIDENCE_MAP.md`
- `docs/THESIS_FINALIZATION_GUIDE.md`
- `reports/VALIDATION_RUN_SUMMARY.md`

Supporting local artifacts:

- `_backup_snapshot_20260527_081434/`
- `reports/validation_logs/20260527_081434/`

## 9. Ablation Evidence Update on 2026-05-30

Before rerunning the ablation script, a new local project snapshot was created:

- `_backup_snapshot_20260530_180650/`

The ablation rerun produced structured outputs under `results/`:

- `results/ablation_propagation.npz`
- `results/ablation_transform.npz`
- `results/ablation_normalization.npz`
- `results/ablation_region.npz`
- `results/ablation_radar_count.npz`
- `results/ablation_summary.json`

Run details:

- `python experiments\ablation_core.py --ablation all --output-dir results` completed A1--A4 and failed at A5 because `ablation_radar_count()` passed an empty polygon list to the normalized evaluator, causing integer modulo by zero during particle evaluation.
- `experiments/ablation_core.py` was fixed so A5 decomposes the rectangle region once and passes the resulting `polygons` and `N_bin` to `create_normalized_evaluate_function`.
- `python experiments\ablation_core.py --ablation radar_count --output-dir results` then completed successfully and saved `results/ablation_radar_count.npz`.
- `tools/summarize_ablation_results.py` generated `results/ablation_summary.json` from the five NPZ files.

Important interpretation:

- The ablation evidence gap is now reduced: the project has structure-level outputs for propagation, coordinate transform, normalization, region shape, and radar count sensitivity.
- This does not yet prove the thesis ablation tables are correct. The next thesis-finalization step is to compare every ablation table entry in `TongjiThesis-1.4.3/chapters/06_experiments.tex` against `results/ablation_summary.json`.

## 10. Scenario JSON Evidence Update on 2026-05-30

Before rerunning the scenario scripts, another local project snapshot was created:

- `_backup_snapshot_20260530_182315/`

The following commands were run with figure output redirected to `C:\tmp` to avoid overwriting current thesis figures:

- `python experiments\experiment_paper_aligned.py --output-dir results --figure-dir C:\tmp\liziqun_paper_aligned_figures`
- `python experiments\experiment_challenging.py --output-dir results --figure-dir C:\tmp\liziqun_challenging_figures`

New structured outputs:

- `results/paper_aligned_results.json`
- `results/challenging_scene_results.json`

Current structured values:

- Paper-Aligned: 7 Pareto solutions, ECR range 0.7800--0.8500, `J_min` range `3.7120569e-06`--`6.0190316e-06`, correlation -0.9231, elapsed 140.8 s.
- Challenging: 10 Pareto solutions, ECR range 0.0311--0.2222, `J_min` range 0.003691--0.009820, correlation -0.9683.

Important interpretation:

- The previous evidence gap for these two single-scenario tables is now closed at the structured-result level.
- The current Paper-Aligned elapsed time differs from older thesis wording that used 156.3 s; later thesis finalization should either update the time to the JSON value or explicitly cite the older run.
- Figures generated in this update were intentionally written to temporary directories, not to the thesis figure directory.
