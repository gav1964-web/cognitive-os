"""Summarize recent goal reports as a field-trial report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = build_report(root, limit=args.limit)
    if args.write:
        report_dir = root / "artifacts" / "field_trials"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = report_dir / f"field_trial_{stamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["report_path"] = path.as_posix()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_report(root: Path, *, limit: int) -> dict[str, Any]:
    reports_dir = root / "artifacts" / "goals" / "reports"
    paths = sorted(reports_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    tasks = [_task_summary(path) for path in paths]
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_count": len(tasks),
        "summary": {
            "actions": _counts(task.get("action") for task in tasks),
            "recommendations": _counts(
                task.get("level4_recommendation") for task in tasks if task.get("level4_recommendation")
            ),
            "selected_alternatives": _counts(
                task.get("selected_alternative") for task in tasks if task.get("selected_alternative")
            ),
            "planners": _counts(task.get("planner") for task in tasks if task.get("planner")),
            "execution": _counts(task.get("execution_status") for task in tasks if task.get("execution_status")),
            "issues": _issues(tasks),
        },
        "tasks": tasks,
    }


def _task_summary(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    decision = dict(report.get("level4_decision", {}))
    deliberation = dict(report.get("level4_deliberation", {}))
    selected_alternative = dict(deliberation.get("selected_alternative") or {})
    plan = dict(report.get("level35_plan", {}))
    execution = dict(report.get("execution", {}))
    dialogue_preflight = report.get("dialogue_preflight")
    return {
        "goal_id": report.get("goal_id"),
        "goal": report.get("goal"),
        "summary": report.get("summary"),
        "action": decision.get("action"),
        "reason_code": decision.get("reason_code"),
        "required_capabilities": decision.get("required_capabilities", []),
        "missing_capability_hint": decision.get("missing_capability_hint"),
        "level4_route": deliberation.get("route"),
        "level4_recommendation": deliberation.get("recommendation"),
        "level4_risk_count": len(deliberation.get("risks", [])),
        "selected_alternative": selected_alternative.get("id"),
        "alternative_count": len(deliberation.get("route_alternatives", [])),
        "planner": plan.get("planner"),
        "template_id": plan.get("template_id"),
        "execution_status": execution.get("status"),
        "completed_nodes": execution.get("completed_nodes", []),
        "dialogue_context": bool(dialogue_preflight),
        "report_path": path.as_posix(),
    }


def _counts(values) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def _issues(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for task in tasks:
        action = task.get("action")
        if action == "PLAN_WITH_L35" and task.get("missing_capability_hint"):
            issues.append({"goal_id": task.get("goal_id"), "issue": "plan_with_missing_capability_hint"})
        if action == "PLAN_WITH_L35" and task.get("execution_status") not in {None, "ok"}:
            issues.append({"goal_id": task.get("goal_id"), "issue": "planned_execution_not_ok"})
        if action in {"ASK_CLARIFICATION", "REQUEST_CAPABILITY_SPEC", "STOP_UNSUPPORTED"} and task.get("execution_status"):
            issues.append({"goal_id": task.get("goal_id"), "issue": "non_execution_action_has_execution"})
    return issues


if __name__ == "__main__":
    raise SystemExit(main())
