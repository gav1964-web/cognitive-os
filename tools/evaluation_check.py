from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TASK_FILES = [
    "prompt.md",
    "direct_agent/README.md",
    "cognitive_os/README.md",
    "metrics.json",
    "verdict.md",
]

REQUIRED_TOP_LEVEL = {
    "task_id",
    "task_class",
    "prompt_hash",
    "routes",
    "comparison",
    "invariants",
    "verdict",
}

REQUIRED_ROUTE_FIELDS = {
    "executor",
    "model",
    "status",
    "requirement_coverage",
    "missed_requirements",
    "invented_requirements",
    "tests_passed",
    "tests_total",
    "verification_status",
    "repair_cycles",
    "runtime_seconds",
    "estimated_cost",
    "artifact_completeness",
    "source_safety_violations",
    "review_blockers",
    "human_correction_minutes",
}

REQUIRED_INVARIANTS = {
    "same_original_prompt",
    "same_constraints",
    "manual_corrections_recorded",
    "teacher_reference_is_ground_truth",
    "source_mutation_detected",
}


def check_evaluation(root: Path) -> dict[str, Any]:
    evaluation_dir = root / "evaluation"
    if not evaluation_dir.exists():
        return {"ok": False, "errors": ["missing evaluation directory"], "tasks": []}

    errors: list[str] = []
    tasks: list[dict[str, Any]] = []
    task_dirs = [
        path
        for path in sorted(evaluation_dir.iterdir())
        if path.is_dir() and path.name.startswith("task") and path.name != "task_template"
    ]

    for task_dir in task_dirs:
        task_errors = _check_task(task_dir)
        tasks.append({"task_id": task_dir.name, "ok": not task_errors, "errors": task_errors})
        errors.extend(f"{task_dir.name}: {error}" for error in task_errors)

    return {
        "ok": not errors,
        "task_count": len(task_dirs),
        "errors": errors,
        "tasks": tasks,
    }


def _check_task(task_dir: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_TASK_FILES:
        if not (task_dir / relative).exists():
            errors.append(f"missing {relative}")

    metrics_path = task_dir / "metrics.json"
    if not metrics_path.exists():
        return errors

    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid metrics.json: {exc}")
        return errors

    missing_top = sorted(REQUIRED_TOP_LEVEL - set(metrics))
    if missing_top:
        errors.append(f"metrics.json missing top-level fields: {missing_top}")

    routes = metrics.get("routes")
    if not isinstance(routes, dict):
        errors.append("metrics.json routes must be an object")
    else:
        for route_name in ("direct_agent", "cognitive_os"):
            route = routes.get(route_name)
            if not isinstance(route, dict):
                errors.append(f"metrics.json routes.{route_name} must be an object")
                continue
            missing_route = sorted(REQUIRED_ROUTE_FIELDS - set(route))
            if missing_route:
                errors.append(f"metrics.json routes.{route_name} missing fields: {missing_route}")

    invariants = metrics.get("invariants")
    if not isinstance(invariants, dict):
        errors.append("metrics.json invariants must be an object")
    else:
        missing_invariants = sorted(REQUIRED_INVARIANTS - set(invariants))
        if missing_invariants:
            errors.append(f"metrics.json invariants missing fields: {missing_invariants}")
        if invariants.get("teacher_reference_is_ground_truth") is True:
            errors.append("teacher_reference_is_ground_truth must not be true")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evaluation task structure.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    report = check_evaluation(Path(args.root))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "ok" if report["ok"] else "failed"
        print(f"evaluation_check: {status}; tasks={report.get('task_count', 0)}")
        for error in report.get("errors", []):
            print(f"- {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

