"""Trial and admit declarative executable-acceptance adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.knowledge_admission import load_kb_candidates
from runtime.promoted_executable_adapters import (
    promote_executable_adapter,
    temporary_executable_adapters,
    validate_executable_adapter,
)


RECORD_TYPE = "foundation_capability_gap"


def run(context: dict[str, Any]) -> dict[str, Any]:
    root = Path(context["root"])
    project_dir = Path(context["project_dir"])
    failure_class = str(dict(context.get("diagnosis") or {}).get("failure_class") or "")
    groups = [row for row in _adapter_groups(root) if row["failure_class"] == failure_class]
    if not groups:
        return {"status": "not_applicable", "reason": "capability_adapter_proposal_missing"}
    minimum = int(dict(context.get("plugin_config") or {}).get("minimum_confirmed_cases") or 3)
    eligible = [row for row in groups if len(row["projects"]) >= minimum]
    if not eligible:
        return {
            "status": "blocked", "reason": "confirmed_cases_required",
            "maximum_confirmed_case_count": max(len(row["projects"]) for row in groups),
            "minimum_confirmed_cases": minimum,
        }
    group = eligible[0]
    if project_dir.name in group["projects"]:
        return {"status": "blocked", "reason": "independent_holdout_required", "adapter_id": group["adapter"]["id"]}
    effect = _holdout_effect(root, project_dir, group["adapter"])
    if effect["status"] != "confirmed_adapter_effect":
        return {
            "status": "blocked", "reason": "holdout_effect_not_confirmed",
            "adapter_id": group["adapter"]["id"], "effect": effect,
        }
    promotion = {"applied": False, "status": "explicit_promotion_required"}
    if context.get("promote"):
        result = promote_executable_adapter(
            root=root,
            adapter=group["adapter"],
            evidence={
                "confirmed_projects": sorted(group["projects"]),
                "holdout_project": project_dir.name,
                "holdout_score_delta": effect["score_delta"],
            },
        )
        promotion = {"applied": result["status"] in {"promoted", "already_promoted"}, **result}
    applied = bool(promotion["applied"])
    return {
        "status": "promoted" if applied else "trial_passed",
        "change_type": "executable_capability_adapter",
        "adapter_id": group["adapter"]["id"],
        "promotion_applied": applied,
        "evolution": {
            "status": "passed", "decision": "accepted",
            "baseline": effect["control"], "shadow": effect["treatment"],
            "promotion": promotion,
            "gates": {
                "repeated_confirmed_cases": True,
                "independent_holdout": True,
                "sandbox_execution_only": True,
                "source_project_unchanged": effect["source_project_unchanged"],
                "no_role_regression": not effect["role_regressions"],
                "raw_llm_code_executed": False,
            },
        },
    }


def _adapter_groups(root: Path) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for candidate in load_kb_candidates(root=root):
        if candidate.get("record_type") != RECORD_TYPE:
            continue
        record = dict(candidate.get("proposed_record") or {})
        proposal = dict(record.get("capability_adapter_proposal") or {})
        adapter = _adapter_from_proposal(proposal)
        if not adapter:
            continue
        fingerprint = hashlib.sha256(
            json.dumps(adapter, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        group = groups.setdefault(fingerprint, {
            "adapter": adapter,
            "failure_class": str(record.get("failure_class") or ""),
            "projects": set(),
        })
        for value in list(candidate.get("source_cases") or []):
            case = dict(value or {})
            if case.get("status") in {"confirmed", "accepted", "verified"} and case.get("project"):
                group["projects"].add(str(case["project"]))
    return sorted(groups.values(), key=lambda row: (-len(row["projects"]), row["adapter"]["id"]))


def _adapter_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get("artifact_type") != "ExecutableCapabilityAdapterProposal":
        return {}
    allowed = {"artifact_type", "id", "kind", "module", "profile"}
    if set(proposal) - allowed or set(dict(proposal.get("profile") or {})) != {"attrs"}:
        return {}
    module = str(proposal.get("module") or "")
    adapter = {
        "id": str(proposal.get("id") or f"generated_module:{module}"),
        "kind": str(proposal.get("kind") or ""),
        "module": module,
        "profile": dict(proposal.get("profile") or {}),
        "activation": "acceptance_sandbox_only",
    }
    try:
        return validate_executable_adapter(adapter)
    except ValueError:
        return {}


def _holdout_effect(root: Path, project_dir: Path, adapter: dict[str, Any]) -> dict[str, Any]:
    from runtime.self_improvement_training import _evaluate, _source_fingerprint

    before = _source_fingerprint(project_dir)
    control = _evaluate(root, project_dir, write=True)
    with temporary_executable_adapters([adapter]):
        treatment = _evaluate(root, project_dir, write=True)
    unchanged = _source_fingerprint(project_dir) == before
    regressions = [
        role for role, score in dict(control.get("role_scores") or {}).items()
        if score is not None and dict(treatment.get("role_scores") or {}).get(role) is not None
        and float(treatment["role_scores"][role]) < float(score)
    ]
    delta = round(float(treatment.get("project_min_score") or 0) - float(control.get("project_min_score") or 0), 2)
    executable = dict(treatment.get("downstream_evidence") or {}).get("acceptance_signal") == "executable_callable"
    same_source = treatment.get("selected_extraction_candidate") == control.get("selected_extraction_candidate")
    confirmed = delta > 0 and executable and same_source and not regressions and unchanged
    return {
        "status": "confirmed_adapter_effect" if confirmed else "adapter_effect_not_confirmed",
        "score_delta": delta,
        "role_regressions": regressions,
        "source_project_unchanged": unchanged,
        "same_selected_source": same_source,
        "control": control,
        "treatment": treatment,
    }
