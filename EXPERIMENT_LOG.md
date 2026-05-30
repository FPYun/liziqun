# Experiment Log

Project: radar deployment optimization with MOPSO-DT

Status: evidence rebuild in progress

Thesis target: Tongji undergraduate thesis

Writing style target: IEEE_CONF academic style

## Artifact Policy

- `results/` is the canonical intake directory for structured result files used by ARIS.
- `figures/` may still contain intermediate outputs and plots, but they are not the final evidence source unless synced into `results/`.
- `TongjiThesis-1.4.0/` is the current thesis source, but numerical claims must still trace back to `results/` and audits.

## Current Local Inputs

- Core code: `src/`
- Experiment scripts: `experiments/`
- Tests: `tests/`
- Existing legacy result JSON: `figures/tune_results.json`
- Existing legacy figures: `figures/*.png`
- Current thesis source: `TongjiThesis-1.4.0/`

## Result Intake Checklist

After rerunning experiments, make sure the following files exist when applicable:

- `results/quick_compare_results.json`
- `results/tune_results.json`
- `results/paper_aligned_results.json`
- `results/challenging_scene_results.json`

You can populate `results/` with:

```powershell
powershell -ExecutionPolicy Bypass -File tools\sync_results.ps1
```

## Claim Discipline

Before any thesis text is treated as final:

1. Run `analyze-results` on the updated JSON files.
2. Run `experiment-audit`.
3. Run `result-to-claim`.
4. Only keep claims that are supported or clearly marked as partial.

## Evidence Gaps To Resolve

- Replace any legacy paper numbers that are not revalidated from updated result files.
- Distinguish normalized objective values from raw physical `J_min`.
- Confirm which experimental scenes and seeds are actually available in the updated result set.
- Rebuild the narrative after the latest code and experiment state, not from stale draft artifacts.

## Run Log

Append experiment runs here after each meaningful execution. Suggested format:

```markdown
## [Run ID or timestamp]
- Command:
- Output file(s):
- Main metrics:
- Notes:
- Verdict: positive | mixed | negative | failed
```
