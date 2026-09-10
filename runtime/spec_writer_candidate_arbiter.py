"""Optional LLM arbitration for close, weak SpecWriter candidates."""

from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .technical_spec_policy import load_technical_spec_policy


ARBITRATION_POLICY = dict(load_technical_spec_policy().get("candidate_arbitration") or {})
NORMAL_CANDIDATE_LIMIT = int(ARBITRATION_POLICY.get("normal_candidate_limit") or 5)
TRAINING_PREFERRED_RANK_LIMIT = int(ARBITRATION_POLICY.get("self_improvement_preferred_rank_limit") or 16)


def arbitrate_candidates(
    ranked: list[dict[str, Any]],
    *,
    config: LocalInferenceConfig | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    preferred = str(dict(config.advisory_context or {}).get("preferred_source") or "") if config else ""
    bounded_sources = {str(row.get("source") or "") for row in ranked[:TRAINING_PREFERRED_RANK_LIMIT]}
    if preferred and preferred in bounded_sources:
        chosen = next(row for row in ranked[:TRAINING_PREFERRED_RANK_LIMIT] if str(row.get("source") or "") == preferred)
        reordered = [chosen, *[row for row in ranked if row is not chosen]]
        chosen["reasons"] = [*list(chosen.get("reasons") or []), "self-improvement challenger selected this bounded source"]
        return reordered, {
            "source": "self_improvement_challenger",
            "llm_invoked": False,
            "eligible": True,
            "accepted": preferred != str(ranked[0].get("source") or ""),
            "selected_source": preferred,
        }
    if config is None or not _needs_arbitration(ranked):
        return ranked, {"source": "deterministic", "llm_invoked": False, "eligible": False}
    candidates = ranked[:NORMAL_CANDIDATE_LIMIT]
    try:
        response = call_json_chat(_messages(candidates, config.advisory_context), config=config)
    except LocalInferenceError as first_error:
        try:
            response = call_json_chat(_retry_messages(candidates[:3]), config=config)
        except LocalInferenceError as exc:
            return ranked, {
                "source": "deterministic_fallback",
                "llm_invoked": False,
                "eligible": True,
                "error": str(exc),
                "retry_reason": str(first_error),
            }
    allowed = {str(row.get("source") or "") for row in candidates}
    selected = str(response.get("selected_source") or "")
    if selected not in allowed:
        return ranked, {
            "source": config.provider_label,
            "model": config.model,
            "llm_invoked": True,
            "eligible": True,
            "accepted": False,
            "reason": "model selected a source outside bounded top-N",
        }
    chosen = next(row for row in ranked if str(row.get("source") or "") == selected)
    reordered = [chosen, *[row for row in ranked if row is not chosen]]
    chosen["reasons"] = [*list(chosen.get("reasons") or []), "bounded LLM arbiter selected this existing top-N source"]
    return reordered, {
        "source": config.provider_label,
        "model": config.model,
        "llm_invoked": True,
        "eligible": True,
        "accepted": selected != str(ranked[0].get("source") or ""),
        "selected_source": selected,
        "reason": str(response.get("reason") or "")[:500],
    }


def _needs_arbitration(ranked: list[dict[str, Any]]) -> bool:
    if len(ranked) < 2:
        return False
    first, second = ranked[:2]
    first_quality = int(first.get("semantic_score") or 0)
    score_gap = int(first.get("score") or 0) - int(second.get("score") or 0)
    return first_quality < 97 and score_gap <= 12


def _messages(candidates: list[dict[str, Any]], training_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    compact = []
    for row in candidates:
        evidence = dict(row.get("evidence") or {})
        compact.append(
            {
                "source": row.get("source"),
                "score": row.get("score"),
                "semantic_score": row.get("semantic_score"),
                "reasons": list(row.get("reasons") or [])[:10],
                "signature": evidence.get("signature"),
                "side_effects": evidence.get("side_effects"),
                "contract_slice_sources": evidence.get("contract_slice_sources"),
                "snippet": evidence.get("snippet"),
            }
        )
    return [
        {
            "role": "system",
            "content": (
                "Select the strongest bounded implementation contract from the supplied candidates. "
                "Return JSON with selected_source and reason. Use an exact supplied source only. "
                "Prefer concrete input/output, deterministic behavior, bounded failure modes, and reusable domain logic. "
                "Avoid callbacks, lifecycle hooks, observers, wrappers, and helpers with hidden side effects when a stronger contract exists."
                " If training_context supplies preferred_source, assess that exact existing candidate first; "
                "use it only when its evidence is stronger than the prior failed target."
            ),
        },
        {"role": "user", "content": json.dumps({"candidates": compact, "training_context": dict(training_context or {})}, ensure_ascii=False, separators=(",", ":"))},
    ]


def _retry_messages(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    compact = [
        {
            "source": row.get("source"),
            "score": row.get("score"),
            "semantic_score": row.get("semantic_score"),
            "reasons": list(row.get("reasons") or [])[:6],
        }
        for row in candidates
    ]
    return [
        {"role": "system", "content": "Return only JSON: selected_source must exactly match one candidate; include reason."},
        {"role": "user", "content": json.dumps({"candidates": compact}, ensure_ascii=False, separators=(",", ":"))},
    ]
