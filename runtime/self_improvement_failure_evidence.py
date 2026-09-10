"""Compact source-backed evidence for autonomous improvement diagnosis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def artifact_evidence(artifacts: dict[str, Any]) -> dict[str, Any]:
    evidence = {}
    for key in ("architecture_decision", "technical_spec"):
        path = dict(artifacts.get(key) or {}).get("path")
        if not path:
            continue
        try:
            payload = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if key == "architecture_decision":
            first_slice = dict(payload.get("first_slice_contract") or {})
            clamp = dict(payload.get("evaluation_target_clamp") or {})
            source_pool = _source_candidate_pool(dict(payload.get("source_context") or {}))
            evidence[key] = {
                "first_slice": {
                    "goal": first_slice.get("goal"),
                    "targets": list(first_slice.get("targets") or [])[:8],
                },
                "risks": [_compact_risk(row) for row in list(payload.get("risks") or [])[:4]],
                "advisory": payload.get("architect_advisory"),
                "evaluation_target_clamp": {
                    "mode": clamp.get("mode"),
                    "target": clamp.get("target"),
                    "candidate_pool": [
                        str(item) for item in list(clamp.get("candidate_pool") or [])[:8]
                    ],
                } if clamp else {},
                "source_candidate_pool": source_pool,
            }
        else:
            contract = dict(payload.get("extraction_contract") or {})
            request = dict(payload.get("first_slice_reselection_request") or {})
            outcome = dict(request.get("outcome") or {})
            evidence[key] = {
                "status": contract.get("status"),
                "candidate": contract.get("candidate"),
                "semantic_quality": compact_candidate_quality(contract.get("semantic_quality", {})),
                "ranked_candidates": [
                    _compact_ranked(row)
                    for row in list(contract.get("ranked_candidates") or [])[:5]
                ],
                "reselection": {
                    "status": request.get("status"),
                    "terminal": bool(request.get("terminal")),
                    "trigger": request.get("trigger"),
                    "resolution_status": request.get("resolution_status"),
                    "outcome_status": outcome.get("status"),
                    "expanded_candidate_count": int(outcome.get("expanded_candidate_count") or 0),
                    "selected_targets": [
                        str(item) for item in list(outcome.get("selected_targets") or [])[:5]
                    ],
                    "viability_rule_ids": _viability_rule_ids(request),
                },
            }
    return evidence


def compact_candidate_quality(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    result = {
        key: row.get(key)
        for key in ("target", "status", "score", "semantic_profile_ids", "contract_archetype_ids")
        if row.get(key) not in (None, "", [])
    }
    structural = dict(row.get("structural_evidence") or {})
    result["structural_evidence"] = {
        key: structural.get(key)
        for key in (
            "argument_count", "argument_usage_types", "literal_return_only",
            "observed_side_effects", "output_inference_basis", "return_paths", "state_mutation",
        )
        if structural.get(key) not in (None, "", [])
    }
    selection = dict(row.get("selection_evidence") or {})
    result["selection_evidence"] = {
        "kind": selection.get("kind"),
        "ranking_reasons": list(selection.get("ranking_reasons") or [])[:6],
        "dependency_readiness": dict(selection.get("dependency_readiness") or {}),
    }
    return result


def minimal_artifact_evidence(value: Any) -> dict[str, Any]:
    evidence = dict(value or {})
    adr = dict(evidence.get("architecture_decision") or {})
    spec = dict(evidence.get("technical_spec") or {})
    return {
        "architecture_decision": {
            "first_slice": adr.get("first_slice"),
            "evaluation_target_clamp": adr.get("evaluation_target_clamp"),
            "source_candidate_pool": list(adr.get("source_candidate_pool") or [])[:12],
        },
        "technical_spec": {
            "status": spec.get("status"),
            "candidate": spec.get("candidate"),
            "semantic_quality": spec.get("semantic_quality"),
            "ranked_candidates": list(spec.get("ranked_candidates") or [])[:3],
            "reselection": spec.get("reselection"),
        },
    }


def reselection_exhausted(packet: dict[str, Any]) -> bool:
    evidence = dict(packet.get("artifact_evidence") or {})
    reselection = dict(dict(evidence.get("technical_spec") or {}).get("reselection") or {})
    return (
        reselection.get("terminal") is True
        and reselection.get("outcome_status") == "exhausted"
        and not list(reselection.get("selected_targets") or [])
    )


def capability_signature(packet: dict[str, Any]) -> str:
    """Name a portable reselection barrier without project-specific source names."""
    evidence = dict(packet.get("artifact_evidence") or {})
    spec = dict(evidence.get("technical_spec") or {})
    reselection = dict(spec.get("reselection") or {})
    ranked = list(spec.get("ranked_candidates") or [])
    selected = str(packet.get("selected_candidate") or "")
    kind = str(dict(ranked[0] or {}).get("kind") or "") if ranked else ""
    if not kind:
        kind = "callable" if ":" in selected else "module_script" if selected.endswith(".py") else "unknown"
    rules = "+".join(sorted(str(item) for item in reselection.get("viability_rule_ids") or []))
    downstream = dict(packet.get("downstream_evidence") or {})
    trigger = str(reselection.get("trigger") or downstream.get("reason") or "unknown")
    if not rules:
        quality = dict(packet.get("candidate_quality") or {})
        structural = dict(quality.get("structural_evidence") or {})
        effects = sorted(str(item) for item in structural.get("observed_side_effects") or [])
        rules = "+".join(effects)
    return "|".join((trigger, rules or "unclassified", kind))


def _compact_ranked(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    return {
        "source": row.get("source"),
        "score": row.get("score"),
        "kind": row.get("kind"),
        "side_effects": list(row.get("side_effects") or [])[:5],
        "reasons": [str(item)[:160] for item in list(row.get("reasons") or [])[:4]],
    }


def _source_candidate_pool(context: dict[str, Any]) -> list[str]:
    rows = []
    for source, value in context.items():
        if ":" not in str(source):
            continue
        row = dict(value or {})
        snippet_value = row.get("snippet")
        snippet = dict(snippet_value) if isinstance(snippet_value, dict) else {}
        structural = dict(snippet.get("structural_contract") or row.get("structural_contract") or {})
        dependency = dict(row.get("dependency_readiness") or {})
        effects = set(str(item) for item in row.get("side_effects") or [])
        effects.update(str(item) for item in structural.get("observed_side_effects") or [])
        binding = str(snippet.get("target_binding") or row.get("target_binding") or "")
        output = str(structural.get("output_inference_basis") or "")
        rows.append((
            int(bool(effects)),
            int(binding not in {"function_symbol", "staticmethod", "classmethod"}),
            int(dependency.get("status") not in {"", "ready"}),
            int(int(structural.get("return_paths") or 0) < 1),
            int(output in {"", "insufficient_structural_evidence", "no_value_return"}),
            _canonical_source_ref(source),
        ))
    rows.sort()
    return [row[-1] for row in rows[:12]]


def _canonical_source_ref(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    return re.sub(r"\s*\(\d+\s+loc\)\s*$", "", text, flags=re.IGNORECASE)


def _compact_risk(value: Any) -> dict[str, Any]:
    row = dict(value or {})
    return {
        key: row.get(key)
        for key in ("description", "evidence", "severity")
        if row.get(key)
    }


def _viability_rule_ids(request: dict[str, Any]) -> list[str]:
    blocking = dict(request.get("blocking_evidence") or {})
    viability = dict(blocking.get("first_slice_viability") or {})
    return sorted({
        str(dict(row or {}).get("rule_id"))
        for row in list(viability.get("matched_rules") or [])
        if dict(row or {}).get("rule_id")
    })
