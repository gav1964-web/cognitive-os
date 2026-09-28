# Package work

Read the relevant package README and `docs/architecture/inspect.md` or
`docs/architecture/replay.md` from the repository root before changing its API.
Implementations live under each package's `src/`; legacy runtime/plugin modules
are adapters. Keep package code independent of `runtime`, `plugins`, `tools`,
role policies and local artifacts. Do not introduce import-path fallbacks.

Run package tests and the affected legacy adapter tests. For dependency, resource
or packaging changes run `python tools/verify_subprojects.py`; source-tree imports
alone cannot verify a distribution. Run `python tools/project_context.py --check`
to validate boundaries and navigation references.
