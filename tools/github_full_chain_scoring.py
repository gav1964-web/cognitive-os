"""Scoring helpers for the GitHub full-chain probe."""

from __future__ import annotations

from typing import Any

from runtime.target_quality import semantic_target_quality_report


CONTROLLED_BLOCK_SCORE = 0.7
META_ONLY_SCORE_CAP = 0.7


def quality_score(checks: list[dict[str, Any]]) -> float:
    return 0.0 if not checks else round(sum(1 for check in checks if check["passed"]) / len(checks), 3)


def selected_target_quality(spec: dict[str, Any], context: str) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract") or {})
    target = str(contract.get("candidate") or "")
    ranked = [str(row.get("source") or "") for row in contract.get("ranked_candidates", []) if isinstance(row, dict)]
    evidence = [str(row.get("source") or "") for row in spec.get("source_evidence", []) if isinstance(row, dict)]
    return semantic_target_quality_report(
        target,
        ranked_candidates=ranked,
        source_evidence=evidence,
        context_evidence=[context],
        selection_reason=str(contract.get("selection_reason") or ""),
        structural_evidence=dict(contract.get("structural_evidence") or {}),
        input_contract=dict(contract.get("input_contract") or {}),
        output_contract=dict(contract.get("output_contract") or {}),
        side_effect_contract=dict(contract.get("side_effects") or {}),
    )


def bounded_quality_score(checks: list[dict[str, Any]], target_quality: dict[str, Any]) -> float:
    structural = quality_score(checks)
    semantic = max(0.0, min(1.0, float(target_quality.get("score") or 0.0) / 100.0))
    return round(min(structural, semantic), 3)


def executor_evidence_ready(executor: dict[str, Any]) -> bool:
    return bool(
        executor.get("executor_status") == "ok"
        and executor.get("executable_acceptance") == "passed"
        and executor.get("acceptance_signal") == "executable_callable"
        and int(executor.get("callable_harness_count") or 0) > 0
    )


def is_controlled_block(spec: dict[str, Any], plan: dict[str, Any], forbidden: list[str]) -> bool:
    contract = dict(spec.get("extraction_contract") or {})
    binding = dict(plan.get("contract_binding") or {})
    return not forbidden and (
        contract.get("status") == "blocked_no_safe_candidate"
        or binding.get("binding_status") == "blocked_no_safe_candidate"
    )


def summary(cases: list[dict[str, Any]], worst_case: float, ready_by_worst_case: bool) -> dict[str, Any]:
    scored = [case for case in cases if case["status"] != "out_of_scope"]
    target_scores = [float(dict(case.get("selected_target_quality") or {}).get("score") or 0.0) for case in scored]
    return {
        "ok": sum(1 for case in cases if case["status"] == "ok"),
        "blocked_no_safe_candidate": sum(1 for case in cases if case["status"] == "blocked_ok"),
        "out_of_scope": sum(1 for case in cases if case["status"] == "out_of_scope"),
        "needs_review": sum(1 for case in cases if case["status"] == "needs_review"),
        "avg_quality_score": round(sum(float(case["quality_score"]) for case in scored) / max(1, len(scored)), 3),
        "worst_case_score": round(worst_case, 3),
        "selected_target_min_score": round(min(target_scores), 2) if target_scores else 0.0,
        "ready_threshold": 0.92,
        "ready_by_worst_case": ready_by_worst_case,
        "contract_violations": sum(int(case["contract_violations"]) for case in cases),
        "architecture_drift": sum(int(case["architecture_drift"]) for case in cases),
        "forbidden_sources": sum(len(case["forbidden_sources"]) for case in cases),
        "source_code_changes": sum(1 for case in cases if case["source_code_changes"]),
        "llm_invoked": sum(1 for case in cases if case["llm_invoked"]),
        "executor_ok": sum(dict(case.get("executor", {})).get("executor_status") == "ok" for case in cases),
        "patch_package_prepared": sum(dict(case.get("executor", {})).get("patch_package_status") == "prepared" for case in cases),
        "patch_synthesis_prepared": sum(dict(case.get("executor", {})).get("patch_synthesis_status") == "prepared" for case in cases),
        "executable_acceptance_passed": sum(dict(case.get("executor", {})).get("executable_acceptance") == "passed" for case in cases),
        "executable_acceptance_callable": sum(
            executor_evidence_ready(dict(case.get("executor") or {})) for case in cases
        ),
        "meta_only_acceptance": sum(
            dict(case.get("executor") or {}).get("acceptance_signal") == "meta_only" for case in cases
        ),
    }
