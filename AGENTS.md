# Pipeline Status

Project: radar deployment optimization with MOPSO-DT

Paper target: Tongji undergraduate thesis

Writing style target: IEEE_CONF academic style

Current ARIS stage: project-update and evidence-rebuild

Primary local paths:
- Project root: this repository
- Reference paper: `An Optimization Method for Multi-Functional Radar Network.pdf`
- Thesis source root: `TongjiThesis-1.4.3/`
- Thesis entry file: `TongjiThesis-1.4.3/main.tex`
- Result intake directory: `results/`
- Audit/report directory: `reports/`

Current state:
- The repository contains working code, experiment scripts, structured results, and the current Tongji thesis source in `TongjiThesis-1.4.3/`.
- The old legacy draft directory and the intermediate `paper-new/` draft have been removed from the cleaned workspace.
- `TongjiThesis-1.4.0/` is retained only as an older local thesis container for comparison, not as the active source of truth.
- Final thesis content must be regenerated from updated project results, not copied from stale draft artifacts.
- Final typesetting and editable thesis source both live in the project-local Tongji thesis template, while narrative style should stay close to IEEE conference writing.
- The working tree already contains user changes. Preserve them unless explicitly asked to revert.

Required workflow order:
1. Update code and rerun experiments.
2. Collect structured result files into `results/`.
3. Run ARIS evidence gates: `analyze-results`, `experiment-audit`, `result-to-claim`.
4. Narrow claims or add missing experiments if needed.
5. Generate `NARRATIVE_REPORT.md` from updated evidence only.
6. Edit validated thesis content directly in `TongjiThesis-1.4.3/chapters/`, `TongjiThesis-1.4.3/bib/note.bib`, and related source files.
7. Compile and audit the final thesis inside `TongjiThesis-1.4.3/`.

Next recommended local commands:

```powershell
python experiments\quick_compare.py
python experiments\tune_mopso.py
python experiments\experiment_paper_aligned.py
python experiments\experiment_challenging.py
powershell -ExecutionPolicy Bypass -File tools\sync_results.ps1
```

Next recommended ARIS commands:

```text
/analyze-results "C:\Users\yunfa\Desktop\liziqun\results\tune_results.json" -- effort: max
/experiment-audit "C:\Users\yunfa\Desktop\liziqun" -- effort: max
/result-to-claim "EXPERIMENT_LOG.md + reports/EXPERIMENT_AUDIT.json" -- effort: max
```
