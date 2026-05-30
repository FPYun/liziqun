# Local Tooling Notes

This file records optional local IDE and agent settings after removing `.aris/`, `.claude/`, and `.vscode/` from the repository workspace.

## ARIS

- `.aris/` was only reserved for ARIS-local state, traces, and helper outputs.
- Canonical project workflow and status live in `AGENTS.md`.
- Tongji template handoff details live in `docs/TONGJI_TEMPLATE_HANDOFF.md`.

## Claude Code

- `CLAUDE.md` is a lightweight entrypoint; canonical project instructions live in `AGENTS.md`.
- `.claude/settings.local.json` is machine-specific and should not be committed.
- Useful permission categories from the previous local config:
  - LaTeX compilation and log inspection.
  - pytest runs for `tests/`.
  - git inspection commands.
  - read-only access to the local Tongji template.
  - legacy Word/format inspection commands, now optional and stale if the referenced `.doc` file is absent.
- Recreate Claude local permissions only when a future local session needs them.

## VS Code

- Python analysis extra path: `src`.
- Python test runner: pytest enabled with args `tests -v --tb=short`.
- Python formatter: Black on save.
- Save actions: organize imports and fix all explicitly.
- Hidden/excluded generated paths: Python caches, pytest cache, coverage output, build/dist artifacts, and `.git`.
- LaTeX Workshop output directory: `%DIR%/../out`.
- Editor rulers: 88, 100, 120.
- Jupyter notebook root: `${workspaceFolder}`.
- Pylance diagnostics:
  - missing imports: warning.
  - missing type stubs: none.
  - unused imports and variables: warning.

## VS Code Debug Configurations

- Current Python file with `PYTHONPATH=${workspaceFolder}/src`.
- Main program: `${workspaceFolder}/src/main.py` if that entry point exists.
- Experiment: `${workspaceFolder}/experiments/experiment_paper_aligned.py`.
- Pytest module over `${workspaceFolder}/tests` with `-v --tb=short`.
- Remote attach on `localhost:5678`.

## VS Code Extension Recommendations

- `ms-python.python`
- `ms-python.vscode-pylance`
- `ms-python.black-formatter`
- `ms-python.isort`
- `charliermarsh.ruff`
- `ms-toolsai.jupyter`
- `james-yu.latex-workshop`
- `eamodio.gitlens`
- `mhutchie.git-graph`
- `yzhang.markdown-all-in-one`
- `oderwat.indent-rainbow`
- `2gua.rainbow-brackets`
- `gruntfuggly.todo-tree`
