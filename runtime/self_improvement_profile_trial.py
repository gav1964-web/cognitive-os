"""Isolated semantic contract profile trial orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .self_improvement_contract_profile import synthesize_contract_profile
from .semantic_target_profiles import temporary_semantic_profiles


def run_profile_trial(
    project_dir: Path,
    sources: list[str],
    evaluate: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    """Try the first evidence-supported profile in a scoped evaluation."""
    for source in sources:
        profile = synthesize_contract_profile(project_dir, source)
        if profile is None:
            continue
        with temporary_semantic_profiles([profile]):
            result = evaluate(source)
        return {
            "parameter_changes": {
                "spec_writer_candidate_preference": source,
                "temporary_semantic_profile": profile,
            },
            "result": result,
        }
    return None
