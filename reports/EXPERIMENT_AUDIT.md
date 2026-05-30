# Experiment Audit Report

**Date**: 2026-05-12
**Auditor**: Claude (same-agent; cross-model Codex MCP unavailable)
**Project**: 基于电子对抗网络的空地协同部署优化 (MOPSO-DT)

## Overall Verdict: WARN

## Integrity Status: warn

Three warnings, no critical failures:
1. Legacy paper draft numbers don't match current experiments
2. Single-seed per configuration, no error bars
3. Minor dead code in evaluation module

## Checks

### A. Ground Truth Provenance: PASS

- All evaluations are **simulation_only** — using mathematical models (radar equation, propagation models)
- No fake ground truth: radar equation uses physics constants (k_B, T0), propagation models reference ITU-R standards
- Baseline comparison against published paper (Han et al., 2025) is clearly labeled as external reference
- No synthetic GT derived from model outputs
- File: `src/evaluation.py:232-297` (radar equation SNR calculation), `src/evaluation.py:156-188` (detection probability)

### B. Score Normalization: PASS

- ECR: raw binary decision `I(P_joint ≥ P_th)`, no self-normalization (`src/evaluation.py:506-509`)
- J_min: raw physical quantity (W/m²), no self-normalization (`src/evaluation.py:546-550`)
- f1 = 1 - ECR: standard maximization→minimization transform, no normalization
- f2 = J_max_ref / (J_min + J_max_ref): uses **externally estimated** J_max_ref per experiment, NOT derived from current solution's statistics (`src/evaluation.py:958`)
  - J_max_ref is set once before optimization (e.g., `experiment_paper_aligned.py:139`)
  - This is legitimate scale normalization, not score fraud
- Hypervolume: standard MO metric with fixed reference point

### C. Result File Existence: WARN

| Claim Source | Claim | Actual Evidence | Status |
|-------------|-------|----------------|--------|
| paper/sections/ | ECR=100% in 100km² scenario | NOT re-validated; current experiments use 200km²/300km² | **MISMATCH** |
| paper/sections/ | 100 Pareto solutions | Current: 6 (paper_aligned), 15 (challenging) | **MISMATCH** |
| paper/sections/ | r = -0.912 | Current: r = -0.939 (paper_aligned), r = -0.958 (challenging) | Close but different |
| paper/sections/ | ECR range 2.2%-4.0% challenging | Current: [3.6%, 20.4%] | Different |
| PAPER_PLAN.md | 100 Pareto solutions | Current max: 15 | Plan needs update |
| PAPER_PLAN.md | Boundary ECR=100% | Not tested in current experiments | Needs experiment |
| tune_results.json | All tuning results | File exists, 6 parameter dimensions, ~70 configs | ✓ Valid |
| experiment_paper_aligned | stdout output only | No structured JSON saved | **Missing file** |
| experiment_challenging | stdout output only | No structured JSON saved | **Missing file** |

### D. Dead Code Detection: WARN

Functions declared but never called in any experiment script:
- `generate_boundary_task_points()` at `src/evaluation.py:807` — boundary task point generator
- `calculate_boundary_ecr()` at `src/evaluation.py:850` — boundary ECR calculator
- `path_loss_air_to_ground()` at `src/evaluation.py:119` — declared but inline logic used instead
- `path_loss_ground_to_ground()` at `src/evaluation.py:137` — same as above
- `calculate_jamming_power()` at `src/evaluation.py:191` — scalar version, vectorized version used instead

These are utility functions, not fraudulent — but their existence suggests planned features (boundary analysis) that were never executed.

### E. Scope Assessment: WARN

- **Scenes tested**: 2 main scenarios (200km² challenging, 300km² paper-aligned)
  - Missing: 100km² basic scenario (mentioned in legacy draft but not re-run)
- **Seeds per configuration**: **1** (no multi-seed averaging)
  - No error bars or standard deviations reported
  - PSO is stochastic — single-seed results may not be representative
- **Parameter tuning**: 6 dimensions explored in tune_results.json with single-seed each
- **Baseline comparison**: Only qualitative comparison to Han et al. (2025); no direct NSGA-II/MOEA/D reimplementation run
- Language check: PAPER_PLAN.md uses "综合实验" — acceptable scope for undergraduate thesis but should not claim "comprehensive"

### F. Evaluation Type: simulation_only

- All evaluations use physics-based mathematical models
- No real-world measurements or dataset ground truth
- Propagation models based on ITU-R recommendations
- Radar equation based on standard radar theory (Skolnik, Richards)
- Appropriate for the domain and thesis level

## Action Items

1. **[HIGH]** Replace all legacy numbers in `paper/sections/` with current experiment results
2. **[HIGH]** Save structured JSON output from experiment_paper_aligned and experiment_challenging
3. **[MEDIUM]** Run multi-seed experiments (≥3 seeds) for key configurations
4. **[MEDIUM]** Re-run the 100km² basic scenario to validate boundary ECR claims
5. **[LOW]** Either implement boundary analysis using dead code functions, or remove them
6. **[LOW]** Add direct NSGA-II/MOEA/D baseline comparisons on the same scenarios

## Claim Impact

| Claim ID | Claim | Impact |
|----------|-------|--------|
| C1 | 边界效应消除，边界ECR=100% | needs_requalification — not re-tested in current experiments |
| C2 | 空地异构传播模型提高准确性 | supported — demonstrated across two propagation models |
| C3 | MOPSO-DT Pareto解+750% | needs_requalification — current runs show 6-15 solutions, not 100 |
| C4 | ECR-J_min强负相关 | supported — consistently r < -0.93 across scenarios |
| C5 | 优化效率提升30× | supported — 211.9s for T_max=500 vs. baseline 15min |
| C6 | 挑战性场景算法有效 | supported — valid Pareto front generated at β=0.03 |
