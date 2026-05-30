# ARIS Thesis Status

This repository is prepared for an ARIS-driven Tongji undergraduate thesis workflow.

## Current Decision

- Main project path: `C:\Users\yunfa\Desktop\liziqun`
- Thesis deliverable: Tongji undergraduate thesis
- Writing style target: `IEEE_CONF`
- Final typesetting container: `TongjiThesis-1.4.0/`
- Final template entry file: `TongjiThesis-1.4.0/main.tex`
- Current stage: rebuild evidence from updated code before generating any final thesis text

## Ground Rules

1. Do not treat stale draft artifacts as the final thesis source.
2. Do not trust legacy numerical claims until they are revalidated from updated result files.
3. Generate narrative content only after `experiment-audit` and `result-to-claim`.
4. Write only audited, evidence-backed content into the project-local Tongji thesis source.

## Working Directories

- Code and experiments: `src/`, `experiments/`, `tests/`
- Structured results: `results/`
- ARIS reports and audits: `reports/`
- Current thesis source: `TongjiThesis-1.4.0/`

## Run Order

### Phase 1. Rebuild Result Artifacts

```powershell
cd C:\Users\yunfa\Desktop\liziqun
python experiments\quick_compare.py
python experiments\tune_mopso.py
python experiments\experiment_paper_aligned.py
python experiments\experiment_challenging.py
powershell -ExecutionPolicy Bypass -File tools\sync_results.ps1
```

### Phase 2. Evidence Gates

```text
/analyze-results "C:\Users\yunfa\Desktop\liziqun\results\tune_results.json" -- effort: max
/experiment-audit "C:\Users\yunfa\Desktop\liziqun" -- effort: max
/result-to-claim "EXPERIMENT_LOG.md + reports/EXPERIMENT_AUDIT.json" -- effort: max
```

### Phase 3. Claim Repair if Needed

```text
/ablation-planner "C:\Users\yunfa\Desktop\liziqun\EXPERIMENT_LOG.md + Tongji undergraduate thesis + IEEE_CONF style" -- effort: max
```

Then rerun the missing experiments and refresh `results/`.

### Phase 4. Content Generation

```text
/auto-review-loop "C:\Users\yunfa\Desktop\liziqun + Tongji undergraduate thesis + IEEE_CONF academic style + current experimental results" -- difficulty: hard, effort: max, human checkpoint: true
/paper-writing "C:\Users\yunfa\Desktop\liziqun\NARRATIVE_REPORT.md" -- venue: IEEE_CONF, effort: max, assurance: submission, human checkpoint: true, style-ref: "C:\Users\yunfa\Desktop\liziqun\An Optimization Method for Multi-Functional Radar Network.pdf"
```

### Phase 5. Template Migration

Use the Tongji template as the final thesis container. Map generated content into:

- `chapters/00_abstract.tex`
- `chapters/02_intro.tex`
- replacement thesis body chapters under `chapters/`
- `chapters/06_conclusion.tex`
- `bib/note.bib`
- `chapters/metadata.tex`

See [docs/TONGJI_TEMPLATE_HANDOFF.md](/C:/Users/yunfa/Desktop/liziqun/docs/TONGJI_TEMPLATE_HANDOFF.md).

### Phase 6. Final Thesis Checks

Run these inside the school template directory after migration:

```text
/paper-compile "TongjiThesis-1.4.0" -- venue: IEEE_CONF
/paper-claim-audit "TongjiThesis-1.4.0" -- effort: max
/citation-audit "TongjiThesis-1.4.0" -- effort: max
```

## Ready-to-Write Gate

Do not migrate final content into the school template until all of the following hold:

- `results/` contains the updated structured outputs you intend to cite.
- `EXPERIMENT_AUDIT.json` exists and its issues are understood.
- `result-to-claim` has either supported or explicitly narrowed the main claims.
- `NARRATIVE_REPORT.md` has been refreshed from updated evidence only.
