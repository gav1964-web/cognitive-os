"""Bounded Stage 2 debug loop for isolated generated packages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_scaffold import run_project_verification
from .greenfield_templates import acceptance_covered
from .programmer_project_review import review_programmer_project


def run_stage2_debug_loop(
    *,
    review_run: dict[str, Any],
    reference: dict[str, Any],
    max_attempts: int = 1,
) -> dict[str, Any]:
    """Analyze a failed package and perform bounded sandbox-only repairs."""
    attempts = []
    current_run = review_run
    for attempt in range(1, max_attempts + 1):
        analysis = analyze_failure(current_run)
        plan = build_rework_plan(analysis, current_run)
        result = apply_rework_plan(current_run, reference, plan)
        attempts.append(
            {
                "attempt": attempt,
                "failure_analysis": analysis,
                "rework_plan": plan,
                "result": result["result"],
            }
        )
        current_run = result["review_run"]
        if current_run.get("status") == "ok":
            break
        if plan["status"] != "ready":
            break
    return {
        "artifact_type": "Stage2DebugLoop",
        "created_at": _now(),
        "max_attempts": max_attempts,
        "attempts": attempts,
        "final_status": current_run.get("status"),
        "final_review_run": current_run,
        "invariants": {
            "sandbox_only": True,
            "source_tree_changes": False,
            "registry_changes": False,
            "bounded_rework": True,
        },
    }


def analyze_failure(review_run: dict[str, Any]) -> dict[str, Any]:
    tester = dict(review_run.get("tester_review", {}))
    checks = dict(tester.get("checks", {}))
    verification = dict(tester.get("verification", {}))
    coverage = dict(tester.get("coverage", {}))
    failed_checks = sorted(key for key, value in checks.items() if value is False)
    failed_commands = [
        {
            "command": item.get("command"),
            "returncode": item.get("returncode"),
            "stdout_tail": item.get("stdout_tail", ""),
            "stderr_tail": item.get("stderr_tail", ""),
        }
        for item in verification.get("commands", [])
        if item.get("status") != "passed"
    ]
    failure_classes = []
    if verification.get("status") != "passed":
        failure_classes.append("verification_failed")
    if coverage.get("missing_acceptance"):
        failure_classes.append("missing_acceptance")
    if failed_checks:
        failure_classes.append("review_check_failed")
    return {
        "artifact_type": "FailureAnalysis",
        "status": "needs_rework" if failure_classes else "clean",
        "failure_classes": failure_classes,
        "failed_checks": failed_checks,
        "failed_commands": failed_commands,
        "missing_acceptance": coverage.get("missing_acceptance", []),
        "repairable": _is_repairable(failed_checks, failed_commands),
    }


def build_rework_plan(analysis: dict[str, Any], review_run: dict[str, Any]) -> dict[str, Any]:
    scaffold = dict(review_run.get("programmer_artifact", {}))
    case = str(scaffold.get("case") or "")
    actions = []
    failed_checks = set(analysis.get("failed_checks", []))
    readme_failures = {"readme_mentions_prompt", "readme_behavior_aligned", "readme_has_run_command"}
    if failed_checks.intersection(readme_failures):
        actions.append({"type": "rewrite_readme_prompt", "target": "README.md"})
    if "has_dependency_policy" in failed_checks:
        actions.append({"type": "repair_dependency_policy", "target": "pyproject.toml"})
    if case == "fastapi_csv_aggregator" and "has_controlled_api_error" in failed_checks:
        actions.append({"type": "repair_fastapi_controlled_400", "target": "src/csv_aggregator_service/app.py"})
    if analysis.get("failed_commands") or actions:
        actions.append({"type": "rerun_verification", "target": "project"})
    return {
        "artifact_type": "ReworkPlan",
        "status": "ready" if actions and (analysis.get("repairable") or _has_actionable_repair(actions)) else "blocked",
        "scope": "isolated_generated_package",
        "actions": actions,
        "forbidden_actions": ["edit_user_source_tree", "edit_registry", "promote_candidate"],
        "reason": "bounded deterministic repair" if actions else "no allowlisted repair for failure",
    }


def apply_rework_plan(review_run: dict[str, Any], reference: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("status") != "ready":
        return {"result": {"status": "blocked", "reason": plan.get("reason")}, "review_run": review_run}
    scaffold = dict(review_run.get("programmer_artifact", {}))
    project_dir = Path(str(scaffold.get("project_dir") or ""))
    applied = []
    for action in plan.get("actions", []):
        action_type = action.get("type")
        if action_type == "rewrite_readme_prompt":
            _rewrite_readme(project_dir, reference)
            applied.append(action_type)
        elif action_type == "repair_dependency_policy":
            if _repair_dependency_policy(project_dir):
                applied.append(action_type)
        elif action_type == "repair_fastapi_controlled_400":
            if _repair_fastapi_controlled_400(project_dir):
                applied.append(action_type)
        elif action_type == "rerun_verification":
            continue
    verification = run_project_verification(project_dir)
    scaffold["verification"] = verification
    scaffold["acceptance_covered"] = acceptance_covered(str(scaffold.get("case") or ""), verification)
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    next_run = dict(review_run)
    next_run["status"] = "ok" if tester_review["recommendation"] in {"approve", "approve_with_risks"} else "needs_rework"
    next_run["programmer_artifact"] = scaffold
    next_run["tester_review"] = tester_review
    return {
        "result": {"status": "applied", "applied_actions": applied, "verification": verification.get("status")},
        "review_run": next_run,
    }


def _is_repairable(failed_checks: list[str], failed_commands: list[dict[str, Any]]) -> bool:
    allowlisted = {
        "readme_mentions_prompt",
        "readme_behavior_aligned",
        "readme_has_run_command",
        "has_dependency_policy",
        "has_controlled_api_error",
    }
    derived = {"verification_passed", "acceptance_complete"}
    direct_checks = set(failed_checks) - derived
    if direct_checks.issubset(allowlisted):
        return True
    return bool(failed_commands) and not direct_checks


def _has_actionable_repair(actions: list[dict[str, Any]]) -> bool:
    return any(action.get("type") != "rerun_verification" for action in actions)


def _rewrite_readme(project_dir: Path, reference: dict[str, Any]) -> None:
    prompt = str(reference.get("prompt") or "")
    app_path = project_dir / "src" / "csv_aggregator_service" / "app.py"
    run_app = "\nRun app: `uvicorn csv_aggregator_service.app:app --app-dir src`.\n" if app_path.is_file() else ""
    (project_dir / "README.md").write_text(
        f"# Generated package\n\nPrompt: {prompt}\n\nRun tests: `python -m pytest tests -q`.\n{run_app}",
        encoding="utf-8",
    )


def _repair_dependency_policy(project_dir: Path) -> bool:
    pyproject = project_dir / "pyproject.toml"
    app_path = project_dir / "src" / "csv_aggregator_service" / "app.py"
    if not pyproject.is_file() or not app_path.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8")
    if "fastapi" in text.lower():
        return False
    if "dependencies" in text:
        text = text.replace("dependencies = []", 'dependencies = ["fastapi"]')
    else:
        text = text.replace("[tool.pytest.ini_options]\n", 'dependencies = ["fastapi"]\n\n[tool.pytest.ini_options]\n')
    pyproject.write_text(text, encoding="utf-8")
    return True


def _repair_fastapi_controlled_400(project_dir: Path) -> bool:
    path = project_dir / "src" / "csv_aggregator_service" / "app.py"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if "HTTPException" in text and "status_code=400" in text:
        return False
    text = text.replace("from fastapi import FastAPI\n", "from fastapi import FastAPI, HTTPException\n")
    old = "    report = aggregate_csv(payload.csv_text)\n    path = save_report(report, payload.output_path)\n"
    new = (
        "    try:\n"
        "        report = aggregate_csv(payload.csv_text)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n"
        "    path = save_report(report, payload.output_path)\n"
    )
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
