"""Typed, evidence-bound change request passed from Spec Writer to execution roles."""

from __future__ import annotations

from typing import Any


_DISCOVERY_GOALS = (
    "assess and prepare first safe transformation",
    "extract first safe capability",
    "assess project",
    "analyze project",
    "проанализируй проект",
    "оцени проект",
)
_CHANGE_MARKERS = (
    " add ", " change ", " fix ", " implement ", " remove ", " replace ",
    "добав", "измен", "исправ", "реализ", "убер", "удал", "замен",
)
_STUB_MARKERS = ("notimplementederror", "raise notimplemented", "todo", "pass")


def build_implementation_delta(
    architecture_decision: dict[str, Any],
    extraction_contract: dict[str, Any],
    acceptance: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify whether the selected target has an evidence-backed code delta."""
    target = str(extraction_contract.get("candidate") or "")
    goal = str(architecture_decision.get("goal") or "").strip()
    acceptance_ids = [str(row.get("id")) for row in acceptance if row.get("id")]
    base = {
        "artifact_type": "ImplementationDelta",
        "target": target or None,
        "acceptance_ids": acceptance_ids[:12],
        "authority": "source_and_user_evidence_only",
        "apply_source_default": False,
    }
    if not target:
        return {
            **base,
            "status": "blocked_no_safe_candidate",
            "intent": None,
            "reason": "No source-backed target is available for a bounded delta.",
            "evidence": [],
        }

    snippet = _candidate_snippet(extraction_contract, target)
    if _explicit_change_goal(goal):
        profile = dict(extraction_contract.get("contract_profile") or {})
        if profile.get("operator_id"):
            return {
                **base,
                "status": "ready",
                "intent": {
                    "kind": "apply_verified_contract_profile",
                    "statement": goal,
                    "operator_id": profile["operator_id"],
                    "profile_id": profile.get("id"),
                },
                "reason": "An explicit change request matches a verified deterministic contract profile.",
                "evidence": [
                    {"source": "ArchitectureDecisionRecord.goal", "value": goal},
                    {"source": str(profile.get("source") or "contract_profile"), "value": profile.get("id")},
                ],
            }
        return {
            **base,
            "status": "semantic_synthesis_required",
            "intent": {"kind": "user_requested_change", "statement": goal},
            "reason": "The requested behavior change is explicit but requires a verified patch hypothesis.",
            "evidence": [{"source": "ArchitectureDecisionRecord.goal", "value": goal}],
        }
    if _source_proves_incomplete(snippet):
        return {
            **base,
            "status": "verification_only",
            "intent": {
                "kind": "characterize_incomplete_candidate",
                "statement": f"Characterize the bounded stub at {target} without inventing missing behavior.",
            },
            "reason": (
                "Stub syntax is an observation only; a target-bound executable failure or explicit "
                "change request is required before synthesis."
            ),
            "evidence": [{"source": target, "value": snippet[:500]}],
        }
    return {
        **base,
        "status": "verification_only",
        "intent": {"kind": "verify_existing_contract", "statement": f"Verify the existing contract at {target} without inventing a behavior change."},
        "reason": "No user-requested or source-proven behavior change is present.",
        "evidence": ([{"source": "ArchitectureDecisionRecord.goal", "value": goal}] if goal else []),
    }


def _explicit_change_goal(goal: str) -> bool:
    normalized = f" {goal.lower()} "
    if any(marker in normalized for marker in _DISCOVERY_GOALS):
        return False
    return any(marker in normalized for marker in _CHANGE_MARKERS)


def _candidate_snippet(contract: dict[str, Any], target: str) -> str:
    for row in list(contract.get("ranked_candidates") or []):
        if str(row.get("source") or row.get("candidate") or "") == target:
            return str(row.get("snippet") or row.get("source_snippet") or "")
    return str(contract.get("candidate_snippet") or "")


def _source_proves_incomplete(snippet: str) -> bool:
    normalized = snippet.lower().strip()
    if not normalized:
        return False
    if normalized == "pass" or normalized.endswith("\n    pass"):
        return True
    return any(marker in normalized for marker in _STUB_MARKERS[:-1])
