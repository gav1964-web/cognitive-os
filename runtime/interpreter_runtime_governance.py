"""Runtime adapter for fail-closed, digest-bound interpreter transitions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .interpreter_authority import (
    InterpreterAuthorityError,
    build_interpreter_decision,
    load_interpreter_authority_policy,
    verify_interpreter_decision,
)


ROLE_STAGES = {
    "project_analyzer": "project_analysis",
    "researcher": "research",
    "architect": "architecture",
    "spec_writer": "specification",
    "implementer": "implementation",
    "task_tree_builder": "implementation",
    "tester": "verification",
    "reviewer": "review",
    "evaluator": "evaluation",
}


class InterpreterRuntimeGovernanceError(RuntimeError):
    """Raised when a runtime boundary cannot produce a verified trace."""


def build_verified_runtime_transition(
    *,
    stage: str,
    next_stage: str,
    goal: str,
    target: str,
    scope: list[str],
    evidence: list[dict[str, Any]],
    rule_id: str,
    outcome: str = "accepted",
    authority_source: str = "config/interpreter_authority.json",
    prior_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = load_interpreter_authority_policy()
    candidates = [
        {
            "candidate_id": candidate,
            "next_stage": candidate,
            "reason": "allowed by interpreter transition policy",
        }
        for candidate in policy["transitions"].get(stage, [])
    ]
    if next_stage not in {row["candidate_id"] for row in candidates}:
        candidates.append({
            "candidate_id": next_stage,
            "next_stage": next_stage,
            "reason": "observed runtime transition; policy validation required",
        })
    try:
        trace = build_interpreter_decision(
            stage=stage,
            goal=goal,
            target=target,
            scope=scope,
            evidence=evidence,
            candidates=candidates,
            selected_candidate_id=next_stage,
            outcome=outcome,
            authority_source=authority_source,
            rule_id=rule_id,
            prior_trace=prior_trace,
            policy=policy,
        )
    except InterpreterAuthorityError as exc:
        raise InterpreterRuntimeGovernanceError(str(exc)) from exc
    verification = verify_interpreter_decision(trace, policy=policy)
    if verification["status"] != "verified":
        raise InterpreterRuntimeGovernanceError("runtime interpreter trace failed verification")
    return trace


def evidence_record(reference: str, value: Any, *, kind: str) -> dict[str, str]:
    return {
        "reference": reference,
        "content_digest": _digest(value),
        "kind": kind,
    }


def project_target_scope(project_report: dict[str, Any]) -> tuple[str, list[str]]:
    context = dict(project_report.get("project_development_context") or {})
    allowed = [str(value) for value in context.get("allowed_targets") or [] if value]
    synthesis = dict(project_report.get("architecture_synthesis") or {})
    first_slice = dict(synthesis.get("recommended_first_slice") or {})
    targets = allowed or [str(value) for value in first_slice.get("targets") or [] if value]
    summary = dict(project_report.get("summary") or {})
    entrypoints = [str(value) for value in summary.get("entrypoints") or [] if value]
    target = (targets or entrypoints or [str(summary.get("root") or "project_scope")])[0]
    scope = targets or entrypoints or [target]
    return target, sorted(set(scope))


def role_stage(role_id: str) -> str:
    return ROLE_STAGES.get(role_id, "controlled_stop")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
