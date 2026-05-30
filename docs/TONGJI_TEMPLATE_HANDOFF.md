# Tongji Template Handoff

This project now keeps a project-local Tongji thesis source at:

- `TongjiThesis-1.4.3/`

The external school template copy is no longer the working source for this repository. Edits and compilation for this project should happen in the local `TongjiThesis-1.4.3/` directory. `TongjiThesis-1.4.0/` is retained only as an older local comparison copy.

## Verified Entry Points

- Main entry: `TongjiThesis-1.4.3/main.tex`
- Metadata: `TongjiThesis-1.4.3/chapters/metadata.tex`
- Abstract: `TongjiThesis-1.4.3/chapters/00_abstract.tex`
- References DB: `TongjiThesis-1.4.3/bib/note.bib`
- Class file: `TongjiThesis-1.4.3/style/tongjithesis.cls`
- Build config: `TongjiThesis-1.4.3/latexmkrc`

## Source of Truth

- Thesis source and final formatting: `TongjiThesis-1.4.3/`.
- Scientific evidence: `results/`, `reports/`, `EXPERIMENT_LOG.md`, and `CLAIMS_FROM_RESULTS.md`.
- Do not edit or restore `paper/`, `paper-new/`, or `tongji_thesis/` as final-format baselines.
- Obsolete migration scripts from `paper-new/` have been removed.
- External table fragments and editable/source figure assets that were absent from the active local module have been archived under `TongjiThesis-1.4.3/tables/` and `TongjiThesis-1.4.3/figures/source/`.

## Repository and Template Responsibilities

Current repository:

- Owns code, experiments, evidence, figures, narrative reports, and the local thesis source.
- Provides scripts for experiment execution, result synchronization, figure generation, and audit support.

Project-local Tongji template:

- Owns final undergraduate thesis layout and compilation.
- Must remain the final-format container for submission output.

## Current Chapter Structure

`TongjiThesis-1.4.3/main.tex` loads these chapter files:

- `chapters/00_abstract.tex`
- `chapters/02_intro.tex`
- `chapters/03_theory.tex`
- `chapters/04_model.tex`
- `chapters/05_algorithm.tex`
- `chapters/06_experiments.tex`
- `chapters/07_conclusion.tex`
- `chapters/appendix.tex`
- `chapters/ack.tex`

The sample guide chapter `chapters/01_guide.tex` is intentionally not part of the local thesis source.

## Style Rule

- Narrative style: IEEE conference style.
- Layout and formatting: Tongji undergraduate thesis template.

That means:

- concise technical prose;
- explicit problem-method-experiment structure;
- restrained claim strength;
- school-required cover, metadata, TOC, and formatting.

## Maintenance Checklist

1. Update project code and rerun experiments when claims change.
2. Sync structured outputs into `results/`.
3. Run `experiment-audit`.
4. Run `result-to-claim`.
5. Refresh `NARRATIVE_REPORT.md`.
6. Edit validated content directly in `TongjiThesis-1.4.3/`.
7. Fill `chapters/metadata.tex` with real student and thesis information.
8. Compile inside `TongjiThesis-1.4.3/`.
9. Run final `paper-claim-audit` and `citation-audit` against `TongjiThesis-1.4.3/`.
