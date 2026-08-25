"""Content identity for resumable foundation self-improvement runs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def improvement_engine_fingerprint(root: Path) -> str:
    root = root.resolve()
    paths = [
        *sorted((root / "runtime").glob("self_improvement*.py")),
        *sorted((root / "runtime").glob("hypothesis_compiler*.py")),
        *sorted((root / "runtime" / "improvement_plugins").glob("*.py")),
        root / "runtime" / "promoted_candidate_selection_policies.py",
        root / "runtime" / "selected_candidate_quality.py",
        root / "config" / "project_evolution_policy.json",
        root / "config" / "self_improvement_plugins.json",
        root / "config" / "hypothesis_compiler.json",
        root / "config" / "technical_spec_policy.json",
    ]
    digest = hashlib.sha256()
    for path in sorted({item for item in paths if item.is_file()}):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
