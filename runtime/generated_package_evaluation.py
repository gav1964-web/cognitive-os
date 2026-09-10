"""Evaluate generated sandbox packages against prompt and runtime evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .sandbox_release_policy import load_sandbox_release_policy, required_checks


def evaluate_generated_package(
    *,
    prompt: str,
    implementation_result: dict[str, Any],
    admission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = dict(implementation_result.get("implementation_plan", {}))
    operation = dict(plan.get("operation", {}))
    recipe = dict(plan.get("operation_recipe", {}))
    contract = dict(plan.get("interface_contract", {}))
    verification = dict(implementation_result.get("verification", {}))
    admission = dict(admission or {})
    available_checks = {
        "prompt_present": bool(prompt.strip()),
        "sandbox_verified": implementation_result.get("status") == "sandbox_verified",
        "verification_passed": verification.get("status") == "passed",
        "operation_selected": bool(operation.get("operation")),
        "operation_has_evidence": bool(operation.get("evidence")),
        "interface_contract_present": bool(contract.get("id")),
        "operation_recipe_present": recipe.get("artifact_type") == "OperationRecipe",
        "recipe_matches_contract": recipe.get("interface_contract") == contract.get("id"),
        "operation_graph_present": dict(plan.get("operation_graph", {})).get("artifact_type") == "SandboxOperationGraph",
        "readme_present": "README.md" in [str(item) for item in implementation_result.get("files", [])],
        "tests_present": any(str(item).startswith("tests/") for item in implementation_result.get("files", [])),
        "tester_admission_passed": admission.get("status") in {None, "passed"},
        "source_not_modified": implementation_result.get("source_code_changes") is False,
        "registry_not_modified": implementation_result.get("registry_changes") is False,
        "promotion_forbidden": implementation_result.get("promotion_allowed") is False,
        "raw_llm_not_executed": dict(implementation_result.get("llm_policy", {})).get("llm_output_executed_directly") is False,
    }
    checks = _select_required_checks(available_checks)
    failed = [name for name, ok in checks.items() if not ok]
    score = round(sum(1 for ok in checks.values() if ok) / len(checks), 3)
    return {
        "artifact_type": "GeneratedPackageEvaluation",
        "status": "passed" if not failed else "needs_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "checks": checks,
        "failed_checks": failed,
        "prompt": prompt,
        "operation": operation.get("operation"),
        "profile": operation.get("profile"),
        "interface_contract": contract.get("id"),
        "transform": recipe.get("transform"),
        "verdict": _verdict(score=score, failed=failed),
    }


def _verdict(*, score: float, failed: list[str]) -> str:
    policy = dict(load_sandbox_release_policy().get("generated_package_evaluation") or {})
    verdicts = dict(policy.get("verdicts") or {})
    if not failed:
        return str(verdicts.get("passed") or "package evidence is complete")
    if score >= float(policy.get("minor_gap_score_threshold") or 0.8):
        return str(verdicts.get("minor_gaps") or "package is likely usable but has evidence gaps")
    return str(verdicts.get("blocked") or "package should not be treated as release-ready without rework")


def _select_required_checks(available_checks: dict[str, bool]) -> dict[str, bool]:
    selected: dict[str, bool] = {}
    for check in required_checks("generated_package_evaluation"):
        selected[check] = available_checks.get(check, False)
    return selected
