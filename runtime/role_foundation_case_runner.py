"""Resource-bounded execution for one foundation field-trial case."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .bounded_process_call import run_bounded_process_call


def run_bounded_foundation_case(
    target: Callable[..., dict[str, Any]], kwargs: dict[str, Any], timeout_seconds: float,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        return target(**kwargs)
    result, timed_out = run_bounded_process_call(
        target, kwargs=kwargs, timeout_seconds=timeout_seconds,
    )
    return _timeout_case(kwargs["project_dir"], timeout_seconds) if timed_out else dict(result or {})


def _timeout_case(project_dir: Path, timeout: float) -> dict[str, Any]:
    roles = {"project_analyzer": 0.0, "architect": 0.0, "spec_writer": 0.0}
    return {
        "project": project_dir.name, "project_dir": project_dir.as_posix(),
        "status": "blocked", "pipeline_status": "not_run",
        "blocker": "field_trial_case_timeout", "role_scores": roles,
        "local_role_scores": roles, "project_min_score": 0.0,
        "selected_extraction_candidate": None, "selected_candidate_quality": {},
        "architect_first_slice": None, "acceptance_signal": "not_measured",
        "downstream_evidence": {"status": "failed", "reason": "resource_budget_exceeded"},
        "warnings": [f"field_trial_case_timeout:{timeout:g}s"],
        "safety": {"source_code_changes": False, "llm_invoked": False},
        "artifacts": {}, "human_documents": {},
    }
