# Working on Cognitive OS

Before live LLM work, check/start the configured local gateway using
`runtime.llm_gateway_bootstrap.ensure_llm_gateway_for_url(root, base_url)`.
The user has authorized this startup; an absent listener is not a user blocker.
Use the configured launcher (hidden background process), verify health readiness,
and keep its receipt. Perform this before starting inference budget accounting.
Do not inspect credentials or alter the gateway's source/config to start it.

Start with `PROJECT_MAP.md`, then `DEVELOPMENT_STATUS.md` and the brief for the
subsystem involved. Also read `DEVELOPMENT_TASKS.md` and the active entries in
`DEVELOPMENT_TASKS.json`. Treat those entries as the incoming work queue: verify
their current source hashes and handle relevant authorized tasks without waiting
for the user to repeat them. For a general continuation, prioritize that queue;
for a narrow task, retain unrelated entries for the next applicable stage.
Generate focused context with:

```bash
python tools/development_stage.py begin
python tools/project_context.py --list
python tools/project_context.py --subsystem replay
python tools/project_context.py --path runtime/durable_queue.py
```

The stage context includes current changes, relevant task entries, test suggestions,
the previous stage receipt and source-bound decisions. Review `needs_review`
decisions before relying on them. Record consequential choices with the `remember`
command; a changed file invalidates the recorded assumption until reviewed.
For a verified stage handoff use `python tools/development_stage.py finish
--test-target <relevant tests> --summary <result>` (repeat `--test-target` as needed).
It runs regression tests even when all files already satisfy the size gate.
General backlog entries are advisory unless explicitly marked `blocking`; do not
turn every future research task into a gate for unrelated engineering work.

Prioritize verified user outcomes over minimizing total architecture size. Keep
each change understandable with bounded, sufficient local context: responsibilities,
contracts, dependencies, consumers and relevant evidence. LLM authorship does not
remove coupling or the need to verify consequences. Split modules or introduce
plugins where these boundaries help; do not add layers or move files merely to
make counts smaller. The final 400-line Python gate still applies, and is not
itself evidence of understandable design. Follow the accepted principles in
`docs/architecture/development_workflow.md` (15 September 2026), including explicit
applicability and fallback for learned deterministic mechanisms and measurement
of quality, cost and latency across the whole task cycle.

Follow `docs/architecture/plugin_owned_knowledge.md`: each domain knowledge item
has an explicit competency-plugin owner. Keep its KB, algorithms, applicability,
contracts and tests together. Shared core/interpreters remain domain-neutral;
do not add competency-specific branches there. Shared catalogs, task context and
evidence journals are infrastructure, not a shared domain KB. Consume another
plugin's knowledge through its versioned contract. Migrate legacy KB together
with consumers and regression evidence, starting with pickle; record temporary
adapters and preserve historical evidence. This is a target architecture, not a
claim that the existing repository has already migrated.

For functional separation stages, success means explicit ownership, domain-neutral
shared code, working contracts and preserved behavior. Do not require a quality
score increase or new external benchmark before continuing a verified extraction.
Keep discovered behavioral defects and quality improvements as separate scoped
tasks; measure them without redefining the purpose of structural migration.

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
During implementation, temporary Python files over 400 lines are allowed:
`python tools/finalize_stage.py --phase development` reports the pending work.
Before completing a development stage or committing, run
`python tools/finalize_stage.py --repair --apply --test-target tests --pytest-plugin pytest_asyncio.plugin`.
This uses the configured L4.5 model only for supported split plans, checks the
unchanged baseline and patched snapshot, and applies only a verified result.
Choose the relevant regression scope for smaller tasks. Unsupported splits must
be completed as ordinary refactoring; a pending finalization is not a completed
stage. The final 400-line gate remains mandatory in canonical verification/CI.
Production capability loading retains its existing size and integrity checks.

The finalizer CLI persists unresolved work in `DEVELOPMENT_TASKS.json` after its
checks, including early unsupported cases and provider failures. Preserve notes
and record concrete next actions when manual design is needed. A smaller or
deleted file remains pending until regression review has evidence; close manual
tasks using the procedure in `DEVELOPMENT_TASKS.md`, then rerun finalization.
Do not use `--no-handoff` to bypass pending work at an ordinary stage boundary.

Update the subsystem brief/manifest when entrypoints or contracts change. Update
current status with the scope, date and receipt of a new measurement; preserve
older evidence as history. Map logical ownership before moving more files.

These navigation instructions do not add approval gates or authorize publishing,
source-corpus mutation, certification or external messages.
