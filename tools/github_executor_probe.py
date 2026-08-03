"""Run Executor over role-produced TestPlans for cloned GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from runtime.programmer_executor import run_programmer_executor
from runtime.project_benchmark import analyze_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_executor_probe")
    parser.add_argument("--write", action="store_true")
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
        run_verification=args.run_verification,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(*, root: Path, projects_dir: Path, label: str, run_verification: bool = False) -> dict[str, Any]:
    cases = [
        _run_case(root=root, project_dir=project_dir, run_verification=run_verification)
        for project_dir in sorted(projects_dir.iterdir())
        if (project_dir / ".git").exists()
    ]
    summary = _summary(cases)
    return {
        "artifact_type": "GitHubExecutorProbe",
        "status": "ok" if summary["ok"] == len(cases) else "needs_review",
        "milestone": label,
        "generated_at": _now(),
        "project_count": len(cases),
        "summary": summary,
        "invariants": {
            "apply_source": False,
            "run_verification": run_verification,
            "source_projects_modified": summary["source_code_changes"],
            "llm_invoked": False,
        },
        "cases": cases,
    }


def _run_case(*, root: Path, project_dir: Path, run_verification: bool) -> dict[str, Any]:
    try:
        before = _git_porcelain(project_dir)
        project_report = analyze_project(project_dir)["project_map_report"]
        artifacts = run_configured_role_prefix(
            goal=f"GitHub Executor probe for {project_dir.name}",
            project_report=project_report,
            until_artifact_type="TestPlan",
        )
        spec = artifact_by_type(artifacts, "TechnicalSpec")
        plan = artifact_by_type(artifacts, "ImplementationPlan")
        test_plan = artifact_by_type(artifacts, "TestPlan")
        result = run_programmer_executor(
            root=root,
            project_dir=project_dir,
            technical_spec=spec,
            implementation_plan=plan,
            test_plan=test_plan,
            run_verification=run_verification,
            apply_source=False,
        )
        test_result = _read_json(result.get("test_result_path"))
        executable = dict(test_result.get("executable_acceptance_result") or {})
        acceptance = dict(executable.get("summary") or {})
        patch = _read_json(result.get("patch_package_path"))
        patch_synthesis = dict(patch.get("patch_synthesis") or {})
        after = _git_porcelain(project_dir)
        ok = result.get("status") == "ok" and executable.get("status") == "passed" and before == after
        boundary_track = _boundary_track(acceptance)
        return {
            "project": project_dir.name,
            "project_dir": project_dir.as_posix(),
            "status": "ok" if ok else "needs_review",
            "executor_status": result.get("status"),
            "test_result_status": test_result.get("status"),
            "executable_acceptance": executable.get("status"),
            "callable_harness_count": acceptance.get("callable_harness_count"),
            "acceptance_signal": acceptance.get("signal_strength"),
            "acceptance_skipped_reasons": acceptance.get("skipped_reason_counts"),
            "acceptance_skipped_targets": acceptance.get("skipped_targets"),
            "boundary_track": boundary_track,
            "patch_synthesis": patch_synthesis.get("status"),
            "patch_reason": patch_synthesis.get("reason"),
            "target": str(dict(plan.get("implementation_target", {})).get("candidate") or ""),
            "source_code_changes": before != after,
        }
    except Exception as exc:  # pragma: no cover - field-trial reporting path.
        return {"project": project_dir.name, "project_dir": project_dir.as_posix(), "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = report_dir / f"{label}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ok": sum(case["status"] == "ok" for case in cases),
        "needs_review": sum(case["status"] == "needs_review" for case in cases),
        "failed": sum(case["status"] == "failed" for case in cases),
        "executor_ok": sum(case.get("executor_status") == "ok" for case in cases),
        "executable_acceptance_passed": sum(case.get("executable_acceptance") == "passed" for case in cases),
        "patch_prepared": sum(case.get("patch_synthesis") == "prepared" for case in cases),
        "patch_skipped": sum(case.get("patch_synthesis") == "skipped" for case in cases),
        "acceptance_callable": sum(case.get("acceptance_signal") == "executable_callable" for case in cases),
        "acceptance_meta_only": sum(case.get("acceptance_signal") == "meta_only" for case in cases),
        "boundary_tracks": _counts(str(case.get("boundary_track") or "unknown") for case in cases),
        "source_code_changes": sum(bool(case.get("source_code_changes")) for case in cases),
    }


def _boundary_track(acceptance: dict[str, Any]) -> str:
    if acceptance.get("signal_strength") == "executable_callable":
        return "pure_python_callable"
    reasons = dict(acceptance.get("skipped_reason_counts") or {})
    details = " ".join(
        str(item.get("detail") or item.get("target") or "")
        for item in list(acceptance.get("skipped_targets") or [])
        if isinstance(item, dict)
    ).lower()
    if any(token in details for token in ("_rust", "_imaging", "crypto.low_level", "zmq.backend")):
        return "native_extension_boundary"
    if reasons.get("import_failed_missing_module") or reasons.get("import_failed_import_error"):
        return "optional_dependency_boundary"
    if reasons.get("positive_sample_execution_failed") or reasons.get("method_target_needs_instance_fixture"):
        return "fixture_or_runtime_shape_boundary"
    return "meta_only_boundary" if acceptance.get("signal_strength") == "meta_only" else "unknown"


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(str(path))
    if not source.is_file():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
