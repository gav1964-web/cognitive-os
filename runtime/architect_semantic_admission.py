"""Semantic admission policy for Architect first-slice reselection."""

from __future__ import annotations

from typing import Any

from .technical_spec_policy import load_technical_spec_policy


def semantic_threshold_satisfied(
    candidate: dict[str, Any], source_context: dict[str, Any] | None, minimum: int
) -> bool:
    if int(candidate.get("semantic_score") or 0) >= minimum:
        return True
    if _has_policy_override(candidate):
        return True
    snippet = dict(dict(source_context or {}).get("snippet") or {})
    structural = dict(snippet.get("structural_contract") or {})
    explicit_return = str(structural.get("explicit_return_annotation") or "").strip().lower()
    return bool(
        explicit_return not in {"", "any", "typing.any", "object", "none", "nonetype"}
        and int(structural.get("typed_argument_count") or 0)
        >= int(structural.get("argument_count") or 0)
    )


def _has_policy_override(candidate: dict[str, Any]) -> bool:
    if str(candidate.get("semantic_status") or "") != "strong":
        return False
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    allowed = {str(value) for value in policy.get("semantic_override_viability_rules") or []}
    matched = {
        str(row.get("rule_id") or "")
        for row in candidate.get("matched_rules") or []
        if isinstance(row, dict)
    }
    return bool(allowed & matched)
