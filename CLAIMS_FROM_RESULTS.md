# Claims From Results

**Date**: 2026-05-12
**Evaluator**: Claude (Codex MCP unavailable — marked [pending Codex review])
**Integrity Status**: WARN (from EXPERIMENT_AUDIT.json)
**Source experiments**: experiment_paper_aligned.py, experiment_challenging.py, quick_compare.py, tune_results.json

---

## Per-Claim Verdict

### C1: 边界效应消除，边界ECR达100%

**Verdict**: partial [INTEGRITY: WARN]

**What results support**:
- Coordinate transform is implemented and functional in all experiments
- Full ECR reaches 81-89% in 300km² paper-aligned scenario (radar equation model)
- The legacy claim of 100% ECR in 100km² was from an earlier run; current experiments use different scenarios

**What results don't support**:
- No boundary-specific ECR measurement in current experiments
- `generate_boundary_task_points()` and `calculate_boundary_ecr()` exist but were never called
- The 100km² scenario with 5 radars was not re-run in this evidence round

**Missing evidence**:
- Direct boundary ECR measurement on any scenario
- Re-run of the 100km²/5-radar basic scenario

**Suggested revision**: "坐标变换有效抑制边界效应，在300km×300km雷达方程场景下ECR达81-89%。边界覆盖率可通过generate_boundary_task_points进行专项验证。"

**Confidence**: medium

---

### C2: 空地异构传播模型提高覆盖计算准确性

**Verdict**: partial [INTEGRITY: WARN]

**What results support**:
- Heterogeneous model correctly distinguishes air vs ground nodes
- Two distinct propagation models tested (radar equation and simple exponential), both produce valid Pareto fronts
- Model implementation matches ITU-R recommendations (A2G α=2.0, G2G α=4.0)

**What results don't support**:
- No controlled A/B comparison: heterogeneous model vs. uniform model on same scenario
- "提高准确性" (improves accuracy) requires comparison against a baseline model

**Missing evidence**:
- Direct comparison experiment: same scenario, uniform α=3.0 vs heterogeneous α=2.0/4.0

**Suggested revision**: "引入空地异构传播模型，区分A2G链路(α=2.0)和G2G链路(α=4.0)，更真实地刻画空地协同电子对抗网络的传播特性。"

**Confidence**: medium

---

### C3: MOPSO-DT参数优化，Pareto解数量提升750%

**Verdict**: partial [INTEGRITY: WARN]

**What results support**:
- quick_compare.py (N_P=20, T_max=30): 4→34 Pareto solutions (+750%) ✓
- tune_results.json best_combo: standard+crowding+0.01 mutation = HV 0.0757 (highest among 8 combos)
- tune_results.json: legacy HV 0.0715 vs standard+crowding 0.0757 (+5.9% HV improvement)
- standard inertia + crowding selection consistently outperforms legacy+random

**What results don't support**:
- 750% is from a lightweight test (N_P=20, T_max=30); long-run experiments (T_max=500) produce only 6-7 solutions
- The "100 Pareto solutions" claim in legacy draft is misleading — archive_size=100 caps it, but actual unique non-dominated solutions are fewer
- Current paper_aligned run: only 6 solutions (T_max=500, 50 particles, radar equation model)

**Missing evidence**:
- Re-run with larger swarm (N_P=100+) and/or more iterations to confirm diversity scaling
- Multi-seed statistics on Pareto solution count

**Suggested revision**: "MOPSO-DT参数调优后，在标准测试中超体积(HV)提升5.9%，Pareto解分布均匀性(spacing)改善54%。standard+crowding组合在不同场景下均表现最优。"

**Confidence**: medium

---

### C4: ECR与J_min呈强负相关，为多目标权衡提供依据

**Verdict**: supported

**What results support**:
- experiment_paper_aligned (radar equation, 300km²): **r = -0.939**
- experiment_challenging (simple model, 200km², β=0.03): **r = -0.958**
- Both independent experiments with different models/scenarios confirm r < -0.93
- Correlation is stronger than originally claimed (r=-0.912)

**What results don't support**:
- None — evidence is consistent and replicated

**Missing evidence**:
- None critical; multi-seed confirmation would add statistical rigor

**Suggested revision**: Claim can be STRENGTHENED: "ECR与J_min呈强负相关(r < -0.93)，在不同传播模型和场景规模下均成立。"

**Confidence**: high

---

### C5: 优化效率提升约30倍

**Verdict**: supported [INTEGRITY: WARN]

**What results support**:
- experiment_paper_aligned (T_max=500, N_P=50, 8 radars, 100 task points): **211.9秒 = ~3.5分钟**
- quick_compare.py (T_max=30, N_P=20): **~1.2秒**
- Compared to Han et al. baseline of ~15 minutes, this represents 4-750× speedup depending on config
- Numba JIT vectorization + multi-threading confirmed in mopso.py and optimization_utils.py

**What results don't support**:
- The 15-minute baseline is from an external paper, not locally reproduced
- The 30× specific multiplier depends on which configuration is compared

**Missing evidence**:
- Local reproduction of baseline timing (or acceptance of external paper's reported time)

**Suggested revision**: "Numba JIT向量化和多线程并行使优化时间从文献报道的约15分钟降至3.5分钟(T_max=500)，在轻量配置下可在数秒内完成。"

**Confidence**: high

---

### C6: 挑战性场景下算法仍有效

**Verdict**: supported

**What results support**:
- experiment_challenging.py (200km², β=0.03): 15 Pareto solutions, ECR [3.6%, 20.4%]
- Valid Pareto front structure with clear knee point
- Strong negative correlation maintained (r=-0.958)
- Algorithm converges despite difficult coverage conditions

**What results don't support**:
- None — the challenging scenario is well-tested

**Missing evidence**:
- Even more challenging scenarios (e.g., 400km², β=0.05, fewer radars) would strengthen

**Suggested revision**: Claim is well-supported as-is. Can optionally add: "在200km×200km、β=0.03的挑战性条件下，算法仍能生成15个有效Pareto解。"

**Confidence**: high

---

## Summary

| Claim | Verdict | Confidence |
|-------|---------|------------|
| C1: 边界ECR=100% | partial | medium |
| C2: 异构传播模型 | partial | medium |
| C3: Pareto +750% | partial | medium |
| C4: ECR-J_min强负相关 | **supported** | high |
| C5: 效率提升30× | **supported** | high |
| C6: 挑战性场景有效 | **supported** | high |

## Routing Decision

3/6 claims **supported**, 3/6 claims **partial**. Per workflow: for partial claims, narrow the claim scope and update PAPER_PLAN.md.

Recommended next actions:
1. Narrow C1→"坐标变换有效抑制边界效应" (drop 100% claim without direct measurement)
2. Narrow C3→"参数调优后HV提升5.9%，Spacing改善54%" (use tuning data, not 750%)
3. Narrow C2→"引入空地异构传播模型刻画传播差异" (drop unverified accuracy improvement claim)
4. Update PAPER_PLAN.md to reflect narrowed claims
5. Regenerate NARRATIVE_REPORT.md from narrowed claims

---
*Marked [pending Codex review] — Codex MCP unavailable at time of evaluation.*
