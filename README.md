# Cognitive OS

Cognitive OS is a contract-driven intent-to-engineering pipeline and verification
harness for LLM-assisted software work. It connects goals, role artifacts,
controlled execution and reproducible evidence. The whole project remains a
research preview; independent product superiority is not established.

Start with the [project map](PROJECT_MAP.md) and
[current development status](DEVELOPMENT_STATUS.md). The map identifies six
subsystems, their entrypoints, contracts, dependencies and focused checks.

## Develop

Python 3.10+ and Git are required. Use a virtual environment, activate it, then
run these commands from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python tools/project_context.py --list
python tools/project_context.py --subsystem replay
python tools/project_context.py --check
```

Development dependencies install both local packages in editable mode. Code
changes belong in their `src/` directories; old runtime/plugin imports remain
compatibility adapters. There are no hidden sys.path fallbacks.

## Subsystems

| Area | Responsibility | Location |
|---|---|---|
| [Inspect](packages/cognitive-inspect/README.md) | Read-only repository facts | `packages/cognitive-inspect/` |
| [Replay](packages/cognitive-replay/README.md) | Repeated defect reproduction and exact-node fix verification | `packages/cognitive-replay/` |
| [Execution](docs/architecture/execution.md) | Pipeline execution, queue leases and recovery | `runtime/` |
| [Evidence](docs/architecture/evidence.md) | Schemas, contracts and artifact integrity | `runtime/`, `registry/` |
| [Roles](docs/architecture/roles.md) | Project analysis, architecture, specifications and review | `runtime/`, `config/` |
| [Research](docs/architecture/research.md) | Corpus admission, training and independent evaluation | `runtime/`, `evaluation/` |

Inspect and Replay are separately installable alpha packages in this monorepo.
Their extraction does not certify the roles or the platform as production-ready.
Other subsystems retain their existing paths and shared integration contracts.

## Verify

Use the selected subsystem's focused test command during development. At an
architecture checkpoint run:

```bash
python tools/canonical_verify.py --root . --write
```

This checks registry/config integrity, the 400-line Python gate, package
boundaries, compilation, core tests, package tests and plugin contracts.
`--skip-tests` is a structural preflight, not release evidence.

Check independently installed distributions, including wheels built from sdists:

```bash
python -m pip install build "setuptools>=77" wheel
python tools/verify_subprojects.py
```

The verifier creates fresh environments, copies tests to a consumer directory and
audits imported package locations. `--wheelhouse PATH` supports a complete offline
dependency wheelhouse. Receipts live under `artifacts/verification/subprojects/`.

## Documentation

Executable behavior is defined by runtime/package code, JSON contracts and
validated configuration. The [technical baseline](COGNITIVE_OS_TECHNICAL_BASELINE.md)
is the engineering specification. [DEVELOPMENT_STATUS](DEVELOPMENT_STATUS.md) is
the current evidence index; [PROJECT_MAP](PROJECT_MAP.md) is the navigation guide.
Historical measurements retain their date and scope.

- [Positioning](POSITIONING.md) and [evaluation plan](EVALUATION_PLAN.md)
- [Three-route evaluation protocol](evaluation/PROTOCOL_V2.md)
- [Historical defect qualification](HISTORICAL_DEFECT_QUALIFICATION.md)
- [Architecture navigation and maintenance](docs/architecture/README.md)
- [Historical reports and the previous detailed operating guide](docs/history/README.md)

## License

[MIT](LICENSE).
