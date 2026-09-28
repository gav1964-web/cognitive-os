"""Build bounded improvement proposals directly from executable evidence."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .promoted_executable_adapters import validate_executable_adapter


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "self_improvement_proposal_recipes.json"


@lru_cache(maxsize=4)
def load_proposal_recipes(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_improvement_proposal_recipes.v1":
        raise ValueError("self-improvement proposal recipes schema mismatch")
    recipes = payload.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise ValueError("self-improvement proposal recipes required")
    seen: set[str] = set()
    for value in recipes:
        recipe = dict(value or {})
        recipe_id = str(recipe.get("id") or "")
        if not recipe_id or recipe_id in seen:
            raise ValueError(f"invalid self-improvement proposal recipe: {recipe_id}")
        if recipe.get("proposal_type") != "capability_adapter_proposal":
            raise ValueError(f"unsupported self-improvement proposal type: {recipe_id}")
        if recipe.get("kind") != "generated_module_profile":
            raise ValueError(f"unsupported executable adapter kind: {recipe_id}")
        if recipe.get("activation") != "acceptance_sandbox_only":
            raise ValueError(f"unsafe executable adapter activation: {recipe_id}")
        if not recipe.get("reason") or not recipe.get("failure_class") or not recipe.get("detail_prefix"):
            raise ValueError(f"incomplete self-improvement proposal recipe: {recipe_id}")
        validate_executable_adapter({
            "id": f"recipe_probe:{recipe_id}",
            "kind": recipe["kind"],
            "module": "proposal_recipe_probe",
            "profile": dict(recipe.get("profile") or {}),
            "activation": recipe["activation"],
        })
        seen.add(recipe_id)
    return payload


def attach_evidence_proposal(packet: dict[str, Any], diagnosis: dict[str, Any]) -> dict[str, Any]:
    result = dict(diagnosis)
    built = build_evidence_proposal(packet)
    if not built:
        return result
    proposed = dict(result.get("proposed_knowledge") or {})
    proposal_type = str(built["proposal_type"])
    previous = proposed.get(proposal_type)
    if previous is not None and previous != built["proposal"]:
        rejections = list(result.get("proposal_rejections") or [])
        rejections.append({
            "proposal": proposal_type,
            "violations": ["superseded_by_executable_acceptance_evidence"],
        })
        result["proposal_rejections"] = rejections
    proposed[proposal_type] = built["proposal"]
    result["proposed_knowledge"] = proposed
    provenance = list(result.get("proposal_provenance") or [])
    provenance.append({
        "proposal": proposal_type,
        "source": "executable_acceptance_evidence",
        "recipe_id": built["recipe_id"],
        "reason": built["reason"],
    })
    result["proposal_provenance"] = provenance
    return result


def build_evidence_proposal(packet: dict[str, Any]) -> dict[str, Any]:
    downstream = dict(packet.get("downstream_evidence") or {})
    summary = dict(downstream.get("summary") or {})
    skipped = [dict(row or {}) for row in list(summary.get("skipped_targets") or [])]
    for recipe_value in load_proposal_recipes()["recipes"]:
        recipe = dict(recipe_value)
        for row in skipped:
            if row.get("reason") != recipe["reason"]:
                continue
            module = _quoted_module(str(row.get("detail") or ""), str(recipe["detail_prefix"]))
            proposal = _proposal(recipe, module)
            if proposal:
                return {
                    "proposal_type": recipe["proposal_type"],
                    "proposal": proposal,
                    "recipe_id": recipe["id"],
                    "reason": recipe["reason"],
                }
    return {}


def _quoted_module(detail: str, prefix: str) -> str:
    marker = detail.find(prefix)
    if marker < 0:
        return ""
    tail = detail[marker + len(prefix):].strip()
    if len(tail) < 3 or tail[0] not in {"'", '"'}:
        return ""
    quote = tail[0]
    end = tail.find(quote, 1)
    return tail[1:end] if end > 1 else ""


def _proposal(recipe: dict[str, Any], module: str) -> dict[str, Any]:
    proposal = {
        "artifact_type": "ExecutableCapabilityAdapterProposal",
        "id": f"generated_module:{module}",
        "kind": recipe["kind"],
        "module": module,
        "profile": dict(recipe["profile"]),
    }
    adapter = {
        key: value for key, value in proposal.items()
        if key not in {"artifact_type"}
    }
    adapter["activation"] = recipe["activation"]
    try:
        validate_executable_adapter(adapter)
    except ValueError:
        return {}
    return proposal
