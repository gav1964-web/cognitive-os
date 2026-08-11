"""Run Project Analyzer -> Architect -> SpecWriter -> Implementer -> Tester -> Reviewer over GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from runtime.programmer_executor import run_programmer_executor
from runtime.role_foundation_field_trial import _primary_language_scope
from runtime.role_project_analysis import analyze_role_project
from runtime.source_target_policy import is_context_only_implementation_target
from tools.github_full_chain_scoring import (
    CONTROLLED_BLOCK_SCORE,
    bounded_quality_score,
    is_controlled_block,
    quality_score as _quality_score,
    selected_target_quality,
    summary as _summary,
)


READY_THRESHOLD = 0.92


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_full_chain_probe")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-executor", action="store_true")
    parser.add_argument("--run-verification", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        run_executor=args.run_executor,
        run_verification=args.run_verification,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(
    *,
    root: Path,
    projects_dir: Path,
    label: str,
    run_executor: bool = False,
    run_verification: bool = False,
) -> dict[str, Any]:
    cases = [
        _run_case(project_dir, root=root, run_executor=run_executor, run_verification=run_verification)
        for project_dir in sorted(projects_dir.iterdir())
        if (project_dir / ".git").exists()
    ]
    scored = [case for case in cases if case["status"] != "out_of_scope"]
    worst_case = min((float(case["quality_score"]) for case in scored), default=0.0)
    ready_by_worst_case = bool(scored) and worst_case >= READY_THRESHOLD and not any(case["status"] == "needs_review" for case in scored)
    return {
        "status": "ok" if ready_by_worst_case and all(case["status"] in {"ok", "blocked_ok", "out_of_scope"} for case in cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": _summary(cases, worst_case, ready_by_worst_case),
        "invariants": {
            "llm_invoked": False,
            "source_projects_modified": any(case["source_code_changes"] for case in cases),
            "registry_changes": False,
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
            "foundry_or_promote_not_in_scope": True,
            "execution_in_scope": run_executor,
            "run_verification": run_verification,
        },
        "cases": cases,
    }


def _run_case(
    project_dir: Path,
    *,
    root: Path | None = None,
    run_executor: bool = False,
    run_verification: bool = False,
) -> dict[str, Any]:
    root = root or Path.cwd()
    language_scope = _primary_language_scope(project_dir)
    if language_scope.get("status") == "out_of_scope":
        return {
            "project": project_dir.name,
            "project_dir": project_dir.as_posix(),
            "status": "out_of_scope",
            "quality_score": 0.0,
            "blocked_reason": language_scope.get("reason") or "unsupported_primary_language_for_python_full_chain",
            "target_chain": {},
            "artifact_status": {},
            "binding_status": None,
            "conformance_status": None,
            "contract_violations": 0,
            "architecture_drift": 0,
            "executor": _executor_not_run(),
            "forbidden_sources": [],
            "llm_invoked": False,
            "source_project_dirty_before": bool(_git_porcelain(project_dir)),
            "source_project_dirty_after": bool(_git_porcelain(project_dir)),
            "source_code_changes": False,
            "failed_checks": [],
        }

    dirty_before = _git_porcelain(project_dir)
    project_report = analyze_role_project(root=root, project_dir=project_dir, goal=f"GitHub full-chain probe for {project_dir.name}")["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"GitHub full-chain probe for {project_dir.name}",
        project_report=project_report,
        until_artifact_type="ReviewFindings",
    )
    adr = artifact_by_type(artifacts, "ArchitectureDecisionRecord")
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    plan = artifact_by_type(artifacts, "ImplementationPlan")
    test_plan = artifact_by_type(artifacts, "TestPlan")
    review = artifact_by_type(artifacts, "ReviewFindings")

    blocked_reason = _blocked_reason(project_report)
    target_chain = _target_chain(adr, spec, plan, test_plan, review)
    forbidden = _forbidden_sources(target_chain, plan, test_plan, review)
    executor = _run_executor(
        root=root,
        project_dir=project_dir,
        spec=spec,
        plan=plan,
        test_plan=test_plan,
        run_executor=run_executor,
        run_verification=run_verification,
    )
    checks = _chain_checks(adr, spec, plan, test_plan, review, target_chain, forbidden, executor, run_executor)
    target_quality = selected_target_quality(spec, project_dir.name)
    quality = bounded_quality_score(checks, target_quality)
    status = "ok" if quality >= READY_THRESHOLD and not forbidden else "needs_review"
    if is_controlled_block(spec, plan, forbidden):
        status = "blocked_ok"
        quality = CONTROLLED_BLOCK_SCORE
        checks = [{"code": "controlled_no_safe_candidate_block", "passed": True}]
    dirty_after = _git_porcelain(project_dir)
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": status,
        "quality_score": quality,
        "selected_target_quality": target_quality,
        "blocked_reason": blocked_reason,
        "target_chain": target_chain,
        "artifact_status": {
            "architecture_decision": adr.get("artifact_type"),
            "technical_spec": spec.get("artifact_type"),
            "implementation_plan": plan.get("artifact_type"),
            "test_plan": test_plan.get("artifact_type"),
            "review_findings": review.get("artifact_type"),
        },
        "binding_status": dict(plan.get("contract_binding", {})).get("binding_status"),
        "conformance_status": review.get("conformance_status"),
        "contract_violations": len(review.get("contract_violations", [])),
        "architecture_drift": len(review.get("architecture_drift", [])),
        "executor": executor,
        "forbidden_sources": sorted(set(forbidden)),
        "llm_invoked": False,
        "source_project_dirty_before": bool(dirty_before),
        "source_project_dirty_after": bool(dirty_after),
        "source_code_changes": dirty_before != dirty_after,
        "failed_checks": [check for check in checks if not check["passed"]],
    }


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = report_dir / f"{label}_{stamp}.json"
    md_path = report_dir / f"{label}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}


def _chain_checks(
    adr: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
    target_chain: dict[str, str],
    forbidden: list[str],
    executor: dict[str, Any],
    run_executor: bool,
) -> list[dict[str, Any]]:
    adr_targets = set(target_chain.get("adr_targets", []))
    spec_target = str(target_chain.get("spec_target", ""))
    implementation_target = target_chain.get("implementation_target", "")
    test_target = target_chain.get("test_target", "")
    review_target = target_chain.get("review_target", "")
    binding = dict(plan.get("contract_binding", {}))
    coverage = dict(review.get("coverage_assessment", {}))
    checks = [
        _check("adr_artifact_ready", adr.get("artifact_type") == "ArchitectureDecisionRecord" and adr.get("role") == producer_for_artifact_type("ArchitectureDecisionRecord")),
        _check("spec_artifact_ready", spec.get("artifact_type") == "TechnicalSpec" and spec.get("role") == producer_for_artifact_type("TechnicalSpec")),
        _check("implementation_artifact_ready", plan.get("artifact_type") == "ImplementationPlan" and plan.get("role") == producer_for_artifact_type("ImplementationPlan")),
        _check("test_artifact_ready", test_plan.get("artifact_type") == "TestPlan" and test_plan.get("role") == producer_for_artifact_type("TestPlan")),
        _check("review_artifact_ready", review.get("artifact_type") == "ReviewFindings" and review.get("role") == producer_for_artifact_type("ReviewFindings")),
        _check("architecture_has_traceability", bool(adr.get("traceability")) and bool(adr.get("source_context"))),
        _check("spec_has_contract", bool(spec_target) and bool(spec.get("source_evidence")) and bool(spec.get("acceptance_criteria"))),
        _check("spec_target_is_advised_by_adr", bool(spec_target) and spec_target in adr_targets),
        _check("target_chain_preserved", bool(spec_target) and spec_target == implementation_target == test_target == review_target),
        _check("implementation_bound_to_spec", binding.get("binding_status") in {"bound_to_extraction_contract", "bound_to_product_contract"}),
        _check("implementation_scope_bounded", list(plan.get("writable_scope", [])) == [implementation_target] and bool(plan.get("patch_scope"))),
        _check("tester_covers_contract", bool(test_plan.get("contract_test_matrix")) and bool(test_plan.get("negative_tests")) and coverage.get("target_covered") is True),
        _check("review_conformance_passed", review.get("conformance_status") == "passed"),
        _check("review_has_no_contract_violations", not review.get("contract_violations")),
        _check("review_has_no_architecture_drift", not review.get("architecture_drift")),
        _check("forbidden_sources_clean", not forbidden and not review.get("forbidden_actions_observed")),
    ]
    if run_executor:
        checks.extend(
            [
                _check("executor_completed", executor.get("executor_status") == "ok"),
                _check("patch_package_prepared", executor.get("patch_package_status") == "prepared"),
                _check("test_result_ok", executor.get("test_result_status") == "ok"),
                _check("executable_acceptance_passed", executor.get("executable_acceptance") == "passed"),
                _check("executor_kept_source_clean", executor.get("source_code_changes") is False),
            ]
        )
    return checks


def _run_executor(
    *,
    root: Path,
    project_dir: Path,
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    run_executor: bool,
    run_verification: bool,
) -> dict[str, Any]:
    if not run_executor:
        return _executor_not_run()
    result = run_programmer_executor(root=root, project_dir=project_dir, technical_spec=spec, implementation_plan=plan, test_plan=test_plan, run_verification=run_verification, apply_source=False)
    test_result = _read_json(result.get("test_result_path"))
    executable = dict(test_result.get("executable_acceptance_result") or {})
    acceptance = dict(executable.get("summary") or {})
    patch = _read_json(result.get("patch_package_path"))
    synthesis = dict(patch.get("patch_synthesis") or {})
    return {
        "executor_status": result.get("status"),
        "execution_dir": result.get("execution_dir"),
        "patch_package_status": patch.get("status"),
        "patch_synthesis_status": synthesis.get("status"),
        "patch_synthesis_reason": synthesis.get("reason"),
        "test_result_status": test_result.get("status"),
        "executable_acceptance": executable.get("status"),
        "callable_harness_count": acceptance.get("callable_harness_count"),
        "acceptance_signal": acceptance.get("signal_strength"),
        "acceptance_skipped_reasons": acceptance.get("skipped_reason_counts"),
        "acceptance_skipped_targets": acceptance.get("skipped_targets"),
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _executor_not_run() -> dict[str, Any]:
    keys = ["patch_package_status", "patch_synthesis_status", "test_result_status", "executable_acceptance", "callable_harness_count", "acceptance_signal", "acceptance_skipped_reasons", "acceptance_skipped_targets"]
    return {"executor_status": "not_run", **{key: None for key in keys}, "source_code_changes": False}


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(str(path))
    return json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}


def _target_chain(
    adr: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    first_slice = dict(adr.get("first_slice_contract", {}))
    brief = dict(adr.get("spec_writer_brief", {}))
    adr_targets = [
        str(item)
        for item in [
            *list(first_slice.get("targets", [])),
            *list(brief.get("files_or_symbols", [])),
        ]
        if item
    ]
    return {
        "adr_targets": sorted(set(adr_targets)),
        "spec_target": str(dict(spec.get("extraction_contract", {})).get("candidate") or ""),
        "implementation_target": str(dict(plan.get("implementation_target", {})).get("candidate") or ""),
        "test_target": str(dict(test_plan.get("test_target", {})).get("candidate") or ""),
        "review_target": str(dict(review.get("review_target", {})).get("candidate") or ""),
    }


def _forbidden_sources(
    target_chain: dict[str, str],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    strategy = dict(test_plan.get("test_strategy", {}))
    values = [
        *[item for value in target_chain.values() for item in (value if isinstance(value, list) else [value])],
        *[str(item) for item in plan.get("patch_scope", [])],
        *[str(item) for item in plan.get("writable_scope", [])],
        *[str(item) for item in strategy.get("writable_scope", [])],
        *[str(item) for item in dict(review.get("coverage_assessment", {})).get("writable_scope", [])],
    ]
    return [value for value in values if _is_forbidden_source(value)]


def _blocked_reason(project_report: dict[str, Any]) -> str:
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    blocked = [str(item) for item in plan.get("blocked_by", [])]
    return "no_safe_python_candidate" if "no_safe_python_candidate" in blocked else ""


def _is_forbidden_source(value: str) -> bool:
    return is_context_only_implementation_target(value)


def _git_porcelain(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "__git_status_unavailable__"
    return result.stdout.strip()


def _check(code: str, passed: bool) -> dict[str, Any]:
    return {"code": code, "passed": bool(passed)}


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [f"# {report['milestone']}", "", f"Generated: `{report['generated_at']}`", f"Projects: `{report['project_count']}`", f"Worst case: `{summary['worst_case_score']}`", f"Ready by worst case: `{summary['ready_by_worst_case']}`", f"Needs review: `{summary['needs_review']}`", "", "## Cases"]
    for case in report["cases"]:
        failed = ", ".join(item["code"] for item in case["failed_checks"]) or "none"
        lines.extend([f"### {case['project']}", f"- status: `{case['status']}`", f"- quality: `{case['quality_score']}`", f"- targets: `{case['target_chain']}`", f"- executor: `{case.get('executor', {})}`", f"- failed checks: `{failed}`", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
