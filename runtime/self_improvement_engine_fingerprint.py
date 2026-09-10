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
        root / "runtime" / "self_development_change.py",
        root / "runtime" / "self_development_shadow_trial.py",
        root / "runtime" / "self_development_prospective_detection.py",
        root / "runtime" / "self_development_collector.py",
        root / "runtime" / "self_development_l0_lifecycle.py",
        root / "runtime" / "self_development_fresh_blind_trial.py",
        root / "runtime" / "self_development_corpus_eligibility.py",
        root / "runtime" / "classification_consistency.py",
        root / "plugins" / "project_map_report" / "src" / "domain_profile.py",
        root / "plugins" / "read_many_files" / "src" / "main.py",
        root / "config" / "project_evolution_policy.json",
        root / "config" / "self_improvement_plugins.json",
        root / "config" / "self_development_change_policy.json",
        root / "config" / "self_development_shadow_trial.json",
        root / "config" / "self_development_prospective_detection.json",
        root / "config" / "self_development_l0_lifecycle.json",
        root / "config" / "self_development_fresh_blind_trial.json",
        root / "config" / "self_development_corpus_eligibility.json",
        root / "config" / "classification_consistency.json",
        root / "config" / "hypothesis_compiler.json",
        root / "config" / "technical_spec_policy.json",
        root / "knowledge" / "architecture_patterns" / "project_archetypes.json",
    ]
    digest = hashlib.sha256()
    for path in sorted({item for item in paths if item.is_file()}):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
