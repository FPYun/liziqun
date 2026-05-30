# Thesis Source Rules

This document keeps the historical migration-rule filename, but the workflow has changed: `paper-new/` has been removed, and `TongjiThesis-1.4.3/` is now the single editable thesis source. `TongjiThesis-1.4.0/` is retained only as an older local comparison copy.

## Priority

1. Thesis source and final formatting: `TongjiThesis-1.4.3/`.
2. Scientific evidence source: `results/`, `reports/`, `EXPERIMENT_LOG.md`, and `CLAIMS_FROM_RESULTS.md`.
3. Word files, PDFs, and legacy drafts are visual references or outputs only; they are not editable source of truth.
4. The simplified `tongji_thesis/`, old `paper/`, and intermediate `paper-new/` directories must not be restored as thesis sources.

## Required Workflow

1. Update code and rerun experiments when claims or numbers change.
2. Sync structured outputs into `results/`.
3. Refresh audits in `reports/`.
4. Update narrative evidence files such as `NARRATIVE_REPORT.md` and `CLAIMS_FROM_RESULTS.md`.
5. Edit thesis content directly in `TongjiThesis-1.4.3/`.
6. Compile from inside `TongjiThesis-1.4.3/`.
7. Audit the compiled thesis output before submission.

## Source Layout

| Thesis content | Source file |
|---|---|
| Main entry | `TongjiThesis-1.4.3/main.tex` |
| Metadata | `TongjiThesis-1.4.3/chapters/metadata.tex` |
| Chinese/English abstract | `TongjiThesis-1.4.3/chapters/00_abstract.tex` |
| Introduction | `TongjiThesis-1.4.3/chapters/02_intro.tex` |
| Theory | `TongjiThesis-1.4.3/chapters/03_theory.tex` |
| Problem model | `TongjiThesis-1.4.3/chapters/04_model.tex` |
| Algorithm design | `TongjiThesis-1.4.3/chapters/05_algorithm.tex` |
| Experiments | `TongjiThesis-1.4.3/chapters/06_experiments.tex` |
| Conclusion | `TongjiThesis-1.4.3/chapters/07_conclusion.tex` |
| Appendices | `TongjiThesis-1.4.3/chapters/appendix.tex` |
| Acknowledgements | `TongjiThesis-1.4.3/chapters/ack.tex` |
| Bibliography | `TongjiThesis-1.4.3/bib/note.bib` |
| Figures used by LaTeX | `TongjiThesis-1.4.3/figures/` |
| Archived source figures | `TongjiThesis-1.4.3/figures/source/` |
| Archived table fragments | `TongjiThesis-1.4.3/tables/` |
| Template class and config | `TongjiThesis-1.4.3/style/` |

## Formatting Rules

Formatting belongs to the `tongjithesis` class and the project-local template files. Do not manually emulate school formatting in prose files or scripts.

Known official template constants:

- Body font: small fourth size (`\zihao{-4}`).
- Body/abstract/TOC line spread: `\tjlinespread = 1.625`, approximating Word 1.5 line spacing.
- Page margins: top `4.0cm`, bottom `2.7cm`, left `3.3cm`, right `1.8cm`.
- Chapter title: black font, small third size.
- Abstract/TOC/reference/acknowledgement heading: fourth size.
- Figure/table captions: small fifth size.
- Table body: small fifth size.

## Content Rules

- Do not copy legacy `paper/` or `paper-new/` text back into the thesis source.
- Do not strengthen claims unless the evidence files support the stronger statement.
- Use "observed in tested scenarios" for ECR--`J_{\min}` correlation unless broader experiments are added.
- Use "minimum equivalent jamming strength" for heterogeneous path-loss models; use physical power-density units only when the model is explicitly free-space with calibrated units.
- Keep metadata fields in `TongjiThesis-1.4.3/chapters/metadata.tex` manually reviewed: college, major, student ID, advisor, thesis type, word count, and attached materials.

## Safety Rules

- `TongjiThesis-1.4.3/main.tex` must use the official `tongjithesis` class.
- `TongjiThesis-1.4.3/main.tex` must not load the template guide chapter `chapters/01_guide.tex`.
- Generated LaTeX build outputs are not source files.
- Figure-generation scripts should write thesis-ready figures into `TongjiThesis-1.4.3/figures/`.
