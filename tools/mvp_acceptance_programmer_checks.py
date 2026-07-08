"""Acceptance checks for programmer prompt curricula."""

from __future__ import annotations

from typing import Any


def programmer_prompt_local_10_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    invariants = dict(payload.get("invariants", {})) if isinstance(payload, dict) else {}
    verdicts = dict(summary.get("verdicts", {}))
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("case_count", 0)) == 10
        and verdicts.get("programmer_ready") == 10
        and float(summary.get("average_maturity", 0.0) or 0.0) == 1.0
        and summary.get("top_backlog") == []
        and invariants.get("teacher_reference_is_ground_truth") is False
        and invariants.get("improvement_protocol") == "external_teacher_corrector_loop"
        and invariants.get("automatic_code_changes_from_own_output") is False
    )
    return ok, f"cases={payload.get('case_count')}, verdicts={verdicts}, backlog={summary.get('top_backlog')}"


def programmer_project_review_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    review = dict(payload.get("tester_review", {})) if isinstance(payload, dict) else {}
    checks = dict(review.get("checks", {}))
    recommendation = review.get("recommendation")
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and dict(payload.get("programmer_artifact", {})).get("artifact_type") == "GreenfieldScaffold"
        and review.get("artifact_type") == "TesterProjectReview"
        and recommendation in {"approve", "approve_with_risks"}
        and checks.get("verification_passed") is True
        and checks.get("acceptance_complete") is True
        and checks.get("project_scoped_verification") is True
        and checks.get("has_negative_or_edge_test") is True
        and checks.get("cli_uses_argparse") is True
        and checks.get("cli_accepts_input_output") is True
        and checks.get("readme_behavior_aligned") is True
        and dict(payload.get("invariants", {})).get("registry_changes") is False
    )
    return ok, f"case={payload.get('case')}, recommendation={recommendation}, checks={checks}"


def verified_system_package_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    gate = dict(payload.get("prompt_adequacy", {})) if isinstance(payload, dict) else {}
    decision = dict(payload.get("release_decision", {}))
    tests = dict(payload.get("tests", {}))
    invariants = dict(payload.get("invariants", {}))
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "VerifiedSystemPackage"
        and payload.get("status") == "ok"
        and gate.get("status") == "ready"
        and decision.get("decision") == "release_ready"
        and tests.get("missing_acceptance") == []
        and bool(payload.get("project_dir"))
        and bool(payload.get("package_report_path"))
        and invariants.get("direct_user_source_modification") is False
        and invariants.get("human_approval_required_for_source_apply") is True
    )
    return ok, f"status={payload.get('status')}, gate={gate.get('status')}, decision={decision.get('decision')}"


def stage2_debug_loop_probe_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    loop = dict(payload.get("debug_loop", {})) if isinstance(payload, dict) else {}
    attempts = list(loop.get("attempts", []))
    first = dict(attempts[0]) if attempts else {}
    result = dict(first.get("result", {}))
    analysis = dict(first.get("failure_analysis", {}))
    invariants = dict(payload.get("invariants", {}))
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "Stage2DebugLoopProbe"
        and payload.get("status") == "ok"
        and loop.get("artifact_type") == "Stage2DebugLoop"
        and loop.get("final_status") == "ok"
        and analysis.get("status") == "needs_rework"
        and bool(result.get("applied_actions"))
        and result.get("verification") == "passed"
        and invariants.get("sandbox_only") is True
        and invariants.get("source_tree_changes") is False
        and invariants.get("registry_changes") is False
        and invariants.get("bounded_rework") is True
    )
    return ok, f"case={payload.get('case')}, final={loop.get('final_status')}, actions={result.get('applied_actions')}"


def product_slice_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    gate = dict(payload.get("prompt_adequacy", {})) if isinstance(payload, dict) else {}
    package = dict(payload.get("verified_system_package", {}))
    release = dict(payload.get("release_decision", {}))
    invariants = dict(payload.get("invariants", {}))
    tasks = list(payload.get("implementation_tasks", []))
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "ProductSliceSpec"
        and payload.get("stage") == "Stage 3"
        and payload.get("status") == "ok"
        and gate.get("status") == "ready"
        and package.get("artifact_type") == "VerifiedSystemPackage"
        and package.get("status") == "ok"
        and release.get("decision") == "slice_ready"
        and len(tasks) >= 5
        and bool(payload.get("product_slice_path"))
        and invariants.get("stage2_package_is_execution_engine") is True
        and invariants.get("prompt_adequacy_gate_required") is True
        and invariants.get("direct_user_source_modification") is False
        and invariants.get("sandbox_only") is True
    )
    return ok, f"status={payload.get('status')}, gate={gate.get('status')}, decision={release.get('decision')}, tasks={len(tasks)}"
