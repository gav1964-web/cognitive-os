# Cognitive Replay

Reproduce one historical Git defect twice, apply its supplied upstream fix in a
temporary worktree, and verify exact pytest nodes. Alpha, Python 3.10+, Git on
PATH. Runtime dependencies: packaging and tomli on Python 3.10.

```bash
python -m pip install ./packages/cognitive-replay
python -m pytest packages/cognitive-replay/tests -q --import-mode=importlib
```

```python
from cognitive_replay import freeze_environment_profile, qualify_candidate_in_sandbox

profile = freeze_environment_profile(root=workspace, wheels=local_wheels)
outcome = qualify_candidate_in_sandbox(
    root=workspace, public=public_case, oracle=sealed_case,
    environment_profile=profile, timeout=180,
)
```

`workspace` is a resolved `pathlib.Path`; wheels must be inside it and include
pytest plus the target's complete dependency set. The frozen profile binds exact
controller Python version, wheel identities and SHA-256. Test subprocesses use
an isolated environment and an included pytest reporting plugin.

`public_case` supplies `project_root` (relative to workspace) and
`baseline_revision`. `sealed_case` supplies `fix_revision`, `test_files`,
`test_entry_files`, `production_files`, `test_patch_sha256` and
`production_patch_sha256`; digests cover the corresponding `git diff` text.
The source repository must have a clean readable Git snapshot.

The outcome includes baseline repeats, fixed results, comparison checks,
environment provenance, cleanup and source-invariant checks. Consumers must check
both `status == "qualified"` and source/cleanup invariants before accepting it.
This API receives the fix: it belongs in the evaluator, not the agent solving a
blind challenge. Worktrees and virtual environments are not an OS security sandbox.

`src/cognitive_replay/` owns replay, process control and metadata helpers.
Corpus mining, public/sealed manifest validation, multi-case admission, role
evaluation and promotion stay in Cognitive OS. Existing runtime imports are
compatibility adapters; receipt/profile versions are unchanged.

Run installed-distribution checks with `python tools/verify_subprojects.py` from
the monorepo. Publishing and product certification remain pending.
