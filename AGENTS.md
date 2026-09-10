# Working on Cognitive OS

Start with `PROJECT_MAP.md`, then `DEVELOPMENT_STATUS.md` and the brief for the
subsystem involved. Generate focused context with:

```bash
python tools/project_context.py --list
python tools/project_context.py --subsystem replay
python tools/project_context.py --path runtime/durable_queue.py
```

Executable behavior is defined by code, contracts and validated configuration.
`COGNITIVE_OS_TECHNICAL_BASELINE.md` is the engineering specification;
`DEVELOPMENT_STATUS.md` is the current evidence/status index. Timestamped reports
and `docs/history/` describe specific past runs. Do not treat old role scores,
training replay or passing harness tests as independent product certification.

Install development dependencies from the repository root:
`python -m pip install -r requirements-dev.txt` (prefer a virtual environment).
This installs the two local packages in editable mode. Implementations live in
`packages/*/src/`; old runtime/plugin paths are compatibility adapters.

Search the relevant source roots (`runtime`, `plugins`, `packages`, `tools`,
`tests`, `registry`, `config`, `knowledge`) first. Avoid recursive searches of
`artifacts`, `.pytest-tmp*`, `.nft`, `.nfi`, generated outputs or external corpora
unless the task needs a specific receipt or fixture. Open the referenced receipt
directly; do not enumerate the entire artifact store. Keep machine-local
`config.json`, credentials and environment files out of context bundles.

Use each subsystem's focused tests during development. Run
`python tools/project_context.py --check` after boundary/navigation changes and
`python tools/canonical_verify.py --root . --write` for an architecture checkpoint.
Run `python tools/verify_subprojects.py` after package/API/dependency changes.
Keep Python files within the existing 400-line gate.

Update the subsystem brief/manifest when entrypoints or contracts change. Update
current status with the scope, date and receipt of a new measurement; preserve
older evidence as history. Map logical ownership before moving more files.

These navigation instructions do not add approval gates or authorize publishing,
source-corpus mutation, certification or external messages.
