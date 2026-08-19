"""Transactional promotion of measured KB/config improvements."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config_mutation_sandbox import materialize_config_mutation, validate_config_mutation
from .project_evolution_policy import load_project_evolution_policy

Evaluator = Callable[[dict[str, Any] | None, Any], dict[str, Any]]


def run_config_evolution(
    *,
    root: Path,
    failure_packet: dict[str, Any],
    proposal: dict[str, Any],
    shadow_case: Any,
    regression_cases: list[Any],
    evaluate: Evaluator,
    promote: bool = False,
) -> dict[str, Any]:
    """Evaluate one bounded mutation and atomically promote it when every gate passes."""
    base = root.resolve()
    packet_hash = _digest(failure_packet)
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    allowed_error = _allowlist_error(proposal, policy)
    validation = _validate(base, proposal) if not allowed_error else {
        "status": "blocked", "validation": {"status": "failed", "errors": [allowed_error]}
    }
    report = _report_skeleton(proposal, packet_hash, validation)
    if validation.get("status") != "passed":
        report["decision"] = "rejected_validation"
        return report

    candidate = materialize_config_mutation(base, proposal)
    target_path = base / str(proposal["target"])
    target_before = target_path.read_bytes()
    baseline = evaluate(None, shadow_case)
    shadow = evaluate(candidate, shadow_case)
    regression = [_compare_case(evaluate, candidate, case) for case in regression_cases]
    target_unchanged = target_path.read_bytes() == target_before
    gates = _promotion_gates(baseline, shadow, regression, policy, target_unchanged)
    report.update({"baseline": baseline, "shadow": shadow, "regression": regression, "gates": gates})
    passed = all(gates.values()) and _digest(failure_packet) == packet_hash
    report["decision"] = "accepted" if passed else "rejected_evidence"
    report["status"] = "passed" if passed else "blocked"
    if passed and promote:
        _atomic_write(target_path, candidate)
        _clear_promoted_policy_cache(str(proposal["target"]))
        report["promotion"] = {"applied": True, "target": target_path.as_posix()}
    else:
        report["promotion"] = {"applied": False, "target": target_path.as_posix()}
    return report


def proposal_from_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any] | None:
    proposed = dict(diagnosis.get("proposed_knowledge") or {})
    value = proposed.get("config_mutation_proposal")
    return dict(value) if isinstance(value, dict) else None


def _allowlist_error(proposal: dict[str, Any], policy: dict[str, Any]) -> str:
    if proposal.get("artifact_type") != "ConfigMutationProposal":
        return "artifact_type_must_be_ConfigMutationProposal"
    if proposal.get("operation") != "merge_object":
        return "self_improvement_requires_merge_object"
    target = str(proposal.get("target") or "").replace("\\", "/")
    pointer = str(proposal.get("path") or "")
    allowed = dict(policy.get("mutable_config_paths") or {})
    if pointer not in list(allowed.get(target) or []):
        return f"mutation_path_not_allowed:{target}:{pointer}"
    return ""


def _validate(root: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(proposal, handle, ensure_ascii=False)
        path = Path(handle.name)
    try:
        return validate_config_mutation(root=root, proposal_path=path)
    finally:
        path.unlink(missing_ok=True)


def _compare_case(evaluate: Evaluator, candidate: dict[str, Any], case: Any) -> dict[str, Any]:
    baseline = evaluate(None, case)
    treatment = evaluate(candidate, case)
    return {
        "case": str(case),
        "baseline": baseline,
        "treatment": treatment,
        "role_regressions": _role_regressions(baseline, treatment),
    }


def _promotion_gates(
    baseline: dict[str, Any],
    shadow: dict[str, Any],
    regression: list[dict[str, Any]],
    policy: dict[str, Any],
    target_unchanged: bool,
) -> dict[str, bool]:
    promotion = dict(policy.get("promotion") or {})
    delta = float(shadow.get("project_min_score") or 0) - float(baseline.get("project_min_score") or 0)
    minimum_delta = float(promotion.get("minimum_score_delta") or 0)
    shadow_ok = shadow.get("status") == "ok" and delta >= minimum_delta
    no_shadow_regression = not _role_regressions(baseline, shadow)
    regression_ok = all(
        row["treatment"].get("status") == "ok" and not row["role_regressions"] for row in regression
    )
    regression_ok = regression_ok and len(regression) >= int(promotion.get("minimum_regression_cases") or 1)
    sources_unchanged = bool(baseline.get("source_project_unchanged", True))
    sources_unchanged = sources_unchanged and bool(shadow.get("source_project_unchanged", True))
    sources_unchanged = sources_unchanged and all(
        row["baseline"].get("source_project_unchanged", True)
        and row["treatment"].get("source_project_unchanged", True)
        for row in regression
    )
    return {
        "validation_passed": True,
        "shadow_improved": shadow_ok if promotion.get("require_shadow_improvement", True) else True,
        "no_shadow_role_regression": no_shadow_regression
        if promotion.get("require_no_role_regression", True) else True,
        "regression_suite_passed": regression_ok
        if promotion.get("require_all_regression_cases_ok", True) else True,
        "active_config_unchanged_during_trials": target_unchanged,
        "source_projects_unchanged": sources_unchanged,
    }


def _role_regressions(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    prior = dict(before.get("role_scores") or {})
    current = dict(after.get("role_scores") or {})
    return sorted(
        role for role, score in prior.items()
        if score is not None and current.get(role) is not None and float(current[role]) < float(score)
    )


def _atomic_write(path: Path, content: dict[str, Any]) -> None:
    encoded = json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _clear_promoted_policy_cache(target: str) -> None:
    if target.replace("\\", "/") == "config/executable_acceptance_policy.json":
        from .executable_acceptance_policy import clear_executable_acceptance_policy_cache

        clear_executable_acceptance_policy_cache()


def _report_skeleton(
    proposal: dict[str, Any], packet_hash: str, validation: dict[str, Any]
) -> dict[str, Any]:
    return {
        "artifact_type": "SelfImprovementEvolutionReport",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "decision": "pending",
        "failure_packet_sha256": packet_hash,
        "proposal": {
            "target": proposal.get("target"),
            "operation": proposal.get("operation"),
            "path": proposal.get("path"),
            "content_sha256": _digest(proposal.get("content")),
        },
        "validation": validation,
    }


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
