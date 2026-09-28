"""Strict quality checks for explicit Programmer transformation trials."""

from __future__ import annotations

from typing import Any


def evaluate_transformation_case(
    *,
    expected_profile: str,
    expected_operator: str,
    source_before: str,
    source_after: str,
    technical_spec: dict[str, Any],
    result: dict[str, Any],
    patch_package: dict[str, Any],
    test_result: dict[str, Any],
) -> dict[str, Any]:
    delta = dict(technical_spec.get("implementation_delta") or {})
    intent = dict(delta.get("intent") or {})
    profile = dict(dict(technical_spec.get("extraction_contract") or {}).get("contract_profile") or {})
    patches = [dict(row) for row in list(patch_package.get("patches") or []) if isinstance(row, dict)]
    patch = patches[0] if patches else {}
    synthesis = dict(patch_package.get("patch_synthesis") or {})
    acceptance = dict(test_result.get("executable_acceptance_result") or {})
    checks = {
        "delta_ready": delta.get("status") == "ready",
        "delta_operator_matches": intent.get("operator_id") == expected_operator,
        "profile_matches": profile.get("id") == expected_profile,
        "executor_completed": result.get("status") == "ok",
        "patch_prepared": synthesis.get("status") == "prepared",
        "single_target_patch": len(patches) == 1 and bool(patch.get("target")),
        "transform_matches": patch.get("transform") == expected_operator,
        "executable_acceptance_passed": acceptance.get("status") == "passed",
        "source_unchanged": source_before == source_after and result.get("source_code_changes") is False,
    }
    score = round(10.0 * sum(checks.values()) / len(checks), 2)
    return {
        "status": "ok" if all(checks.values()) else "needs_review",
        "score": score,
        "checks": checks,
        "delta_status": delta.get("status"),
        "delta_intent": intent,
        "profile_id": profile.get("id"),
        "operator_id": profile.get("operator_id"),
        "patch_reason": synthesis.get("reason"),
        "patch_transform": patch.get("transform"),
        "patch_count": len(patches),
        "acceptance_status": acceptance.get("status"),
    }


def transformation_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(case.get("score") or 0.0) for case in cases]
    return {
        "accepted": sum(case.get("status") == "ok" for case in cases),
        "needs_review": sum(case.get("status") != "ok" for case in cases),
        "minimum_score": min(scores, default=0.0),
        "project_count": len({str(case.get("project")) for case in cases if case.get("project")}),
        "profiles": _counts(case.get("profile_id") for case in cases),
        "operators": _counts(case.get("operator_id") for case in cases),
        "patch_reasons": _counts(case.get("patch_reason") for case in cases),
        "patch_transforms": _counts(case.get("patch_transform") for case in cases),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))
