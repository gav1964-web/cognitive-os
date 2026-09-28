"""Build replayable authority traces for configuration-driven decisions."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "interpreter_authority.json"


class InterpreterAuthorityError(ValueError):
    """Raised when an interpreter decision cannot be represented safely."""


@lru_cache(maxsize=2)
def load_interpreter_authority_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "interpreter_authority.v1":
        raise InterpreterAuthorityError("interpreter authority schema mismatch")
    if payload.get("status") != "active":
        raise InterpreterAuthorityError("interpreter authority policy must be active")
    if not payload.get("stage_sequence") or not payload.get("transitions"):
        raise InterpreterAuthorityError("interpreter authority routes are incomplete")
    recovery = dict(payload.get("recovery") or {})
    if int(recovery.get("maximum_returns") or 0) < 1:
        raise InterpreterAuthorityError("interpreter recovery must be bounded")
    if recovery.get("scope_expansion_forbidden") is not True:
        raise InterpreterAuthorityError("interpreter recovery may not expand scope")
    if dict(payload.get("product_surface") or {}).get("web_ui_is_current_milestone") is not False:
        raise InterpreterAuthorityError("web UI must remain deferred")
    return payload


def build_interpreter_decision(
    *,
    stage: str,
    goal: str,
    target: str,
    scope: list[str],
    evidence: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    selected_candidate_id: str,
    outcome: str,
    authority_source: str,
    rule_id: str,
    prior_trace: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_interpreter_authority_policy()
    _require_non_empty(stage=stage, goal=goal, target=target, rule_id=rule_id)
    if stage not in rules["transitions"]:
        raise InterpreterAuthorityError(f"unknown interpreter stage: {stage}")
    if outcome not in set(rules["allowed_outcomes"]):
        raise InterpreterAuthorityError(f"unknown interpreter outcome: {outcome}")
    if not any(authority_source.startswith(prefix) for prefix in rules["authority_source_prefixes"]):
        raise InterpreterAuthorityError("decision authority must be config, knowledge, or registry")
    normalized_evidence = _evidence(evidence, rules)
    normalized_candidates = _candidates(candidates)
    selected = next(
        (row for row in normalized_candidates if row["candidate_id"] == selected_candidate_id),
        None,
    )
    if selected is None:
        raise InterpreterAuthorityError("selected candidate is absent from alternatives")

    violations = []
    next_stage = str(selected["next_stage"])
    if next_stage not in set(rules["transitions"][stage]):
        violations.append("transition_not_allowed")
    prior = dict(prior_trace or {})
    recovery_count = int(prior.get("recovery_count") or 0)
    if outcome in {"needs_rework", "research_more"}:
        recovery_count += 1
    if recovery_count > int(rules["recovery"]["maximum_returns"]):
        violations.append("recovery_budget_exceeded")
    if prior:
        prior_verification = verify_interpreter_decision(prior, policy=rules)
        if prior_verification["status"] != "verified":
            violations.append("prior_trace_invalid")
        if prior.get("goal_digest") != _digest(goal):
            violations.append("goal_changed")
        if prior.get("target") != target:
            violations.append("target_changed")
        if not set(scope).issubset(set(prior.get("scope") or [])):
            violations.append("scope_expanded")
        if prior.get("next_stage") != stage:
            violations.append("prior_transition_not_consumed")
    if outcome == "controlled_stop" and next_stage != "controlled_stop":
        violations.append("controlled_stop_route_mismatch")

    snapshot = {
        "stage": stage,
        "goal": goal,
        "target": target,
        "scope": sorted(set(scope)),
        "evidence": normalized_evidence,
        "candidates": normalized_candidates,
    }
    body = {
        "artifact_type": "InterpreterDecisionTrace",
        "schema_version": "interpreter_decision_trace.v1",
        "status": "accepted" if not violations else "controlled_stop",
        "stage": stage,
        "outcome": outcome if not violations else "controlled_stop",
        "next_stage": next_stage if not violations else "controlled_stop",
        "goal_digest": _digest(goal),
        "target": target,
        "scope": snapshot["scope"],
        "input_digest": _digest(snapshot),
        "evidence_digest": _digest(normalized_evidence),
        "input_snapshot": snapshot,
        "alternatives": normalized_candidates,
        "selected_candidate_id": selected_candidate_id,
        "authority": {"source": authority_source, "rule_id": rule_id},
        "prior_trace_digest": prior.get("trace_digest"),
        "recovery_count": recovery_count,
        "violations": violations,
        "constraints": {
            "execution_authorized": False,
            "source_apply": False,
            "automatic_promotion": False,
            "automatic_retry": False,
        },
    }
    return {**body, "trace_digest": _digest(body)}


def verify_interpreter_decision(
    trace: dict[str, Any], *, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    rules = policy or load_interpreter_authority_policy()
    errors = []
    body = {key: value for key, value in trace.items() if key != "trace_digest"}
    snapshot = dict(trace.get("input_snapshot") or {})
    if trace.get("trace_digest") != _digest(body):
        errors.append("trace_digest_mismatch")
    if trace.get("input_digest") != _digest(snapshot):
        errors.append("input_digest_mismatch")
    if trace.get("evidence_digest") != _digest(snapshot.get("evidence") or []):
        errors.append("evidence_digest_mismatch")
    if trace.get("next_stage") not in set(rules["transitions"].get(trace.get("stage"), [])) | {"controlled_stop"}:
        errors.append("transition_not_allowed")
    return {
        "artifact_type": "InterpreterDecisionVerification",
        "status": "verified" if not errors else "invalid",
        "trace_digest": trace.get("trace_digest"),
        "errors": errors,
    }


def _evidence(rows: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    required = set(policy["required_evidence_fields"])
    normalized = []
    for raw in rows:
        row = dict(raw)
        if not required.issubset(row):
            raise InterpreterAuthorityError("interpreter evidence is incomplete")
        digest = str(row.get("content_digest") or "")
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise InterpreterAuthorityError("interpreter evidence digest is invalid")
        normalized.append({key: row[key] for key in sorted(row)})
    if not normalized:
        raise InterpreterAuthorityError("interpreter decision requires evidence")
    return sorted(normalized, key=lambda row: (str(row["kind"]), str(row["reference"])))


def _candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in rows]
    ids = [str(row.get("candidate_id") or "") for row in normalized]
    if not normalized or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise InterpreterAuthorityError("interpreter alternatives require unique candidate ids")
    if any(not row.get("next_stage") or not row.get("reason") for row in normalized):
        raise InterpreterAuthorityError("interpreter alternative is incomplete")
    return sorted(normalized, key=lambda row: str(row["candidate_id"]))


def _require_non_empty(**values: str) -> None:
    missing = [name for name, value in values.items() if not str(value).strip()]
    if missing:
        raise InterpreterAuthorityError(f"interpreter decision requires {missing[0]}")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
