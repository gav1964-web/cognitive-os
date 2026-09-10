"""Assemble a truthful authority report for the next Cognitive OS evolution step."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .interpreter_authority import load_interpreter_authority_policy, verify_interpreter_decision
from .self_development_experiment import verify_self_development_experiment


def build_evolution_authority_report(
    *,
    interpreter_trace: dict[str, Any],
    role_chain_summary: dict[str, Any],
    corpus_plan: dict[str, Any],
    evidence_root: Path | None = None,
    narrow_certification: dict[str, Any] | None = None,
    self_development_experiment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    certification = dict(narrow_certification or {})
    experiment = dict(self_development_experiment or {})
    policy = load_interpreter_authority_policy()
    interpreter_verification = verify_interpreter_decision(interpreter_trace, policy=policy)
    corpus_checks = dict(corpus_plan.get("checks") or {})
    checks = {
        "interpreter_trace_verified": interpreter_verification.get("status") == "verified",
        "role_handoff_loss_zero": int(role_chain_summary.get("handoff_loss_count") or 0) == 0,
        "blocked_role_returns_zero": int(role_chain_summary.get("blocked_role_return_count") or 0) == 0,
        "corpus_split_disjoint": corpus_checks.get("split_content_disjoint") is True
        and corpus_checks.get("split_lineage_disjoint") is True,
        "network_fallback_policy_preserved": (
            dict(corpus_plan.get("network_fallback") or {}).get("allowed")
            == (corpus_plan.get("status") == "local_corpus_shortage")
        ),
        "narrow_certification_truthful": not certification
        or (
            certification.get("status") == "certified"
            and certification.get("promotion_eligible") is True
        )
        or (
            certification.get("status") == "evidence_required"
            and certification.get("promotion_eligible") is False
        ),
        "self_development_is_bounded": not experiment
        or verify_self_development_experiment(experiment, evidence_root=evidence_root)
        or experiment.get("status") == "rejected",
        "generated_function_stubs_absent": not experiment
        or int(experiment.get("generated_stub_count") or 0) == 0,
        "web_ui_deferred": dict(policy.get("product_surface") or {}).get("web_ui_is_current_milestone") is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    next_action = _next_action(
        failed=failed,
        corpus=corpus_plan,
        certification=certification,
        experiment=experiment,
    )
    if failed:
        status = "blocked"
    elif certification.get("status") == "certified":
        status = "narrow_lane_certified"
    else:
        status = "ready_for_narrow_evaluation"
    body = {
        "artifact_type": "CognitiveOSEvolutionAuthorityReport",
        "schema_version": "cognitive_os_evolution_authority.v1",
        "status": status,
        "checks": checks,
        "failed_checks": failed,
        "interpreter": {
            "trace_digest": interpreter_trace.get("trace_digest"),
            "verification": interpreter_verification,
        },
        "role_chain": dict(role_chain_summary),
        "narrow_certification": certification or {"status": "not_run"},
        "self_development_experiment": experiment or {"status": "not_run"},
        "corpus": {
            "status": corpus_plan.get("status"),
            "summary": dict(corpus_plan.get("summary") or {}),
            "shortages": dict(corpus_plan.get("shortages") or {}),
            "network_fallback": dict(corpus_plan.get("network_fallback") or {}),
        },
        "next_action": next_action,
        "product_surface": dict(policy["product_surface"]),
        "safety": {
            "source_apply": False,
            "automatic_promotion": False,
            "web_ui_work_authorized": False,
        },
    }
    return {**body, "report_digest": _digest(body)}


def _next_action(
    *, failed: list[str], corpus: dict[str, Any], certification: dict[str, Any], experiment: dict[str, Any]
) -> str:
    if failed:
        return "repair_authority_gates"
    if corpus.get("status") == "local_corpus_shortage":
        return "fill_local_shortage_then_allow_targeted_acquisition"
    if not certification or certification.get("status") != "certified":
        return "run_independent_narrow_type_holdout"
    if experiment and experiment.get("status") == "staging_eligible":
        return "request_external_review_for_bounded_staging"
    return "select_repeated_error_for_bounded_l0_l1_experiment"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
