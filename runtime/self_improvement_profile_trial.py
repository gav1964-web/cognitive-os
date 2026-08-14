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
        control = evaluate(source)
        with temporary_semantic_profiles([profile]):
            result = evaluate(source)
        if not _same_selected_source(source, control, result):
            continue
        profile_delta = round(result["project_min_score"] - control["project_min_score"], 2)
        return {
            "parameter_changes": {
                "spec_writer_candidate_preference": source,
                "temporary_semantic_profile": profile,
            },
            "control_result": control,
            "result": result,
            "profile_score_delta": profile_delta,
        }
    return None


def _same_selected_source(source: str, control: dict[str, Any], treatment: dict[str, Any]) -> bool:
    return all(str(row.get("selected_extraction_candidate") or "") == source for row in (control, treatment))
