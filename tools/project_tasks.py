"""Inspect project-analysis tasks and create Foundry spec requests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


_SPEC_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", default=None, help="Read one goal report instead of all reports.")
    parser.add_argument("--project", default=None, help="Filter by substring in goal or root input path.")
    parser.add_argument("--type", default=None, help="Filter by analysis task type.")
    parser.add_argument("--priority", default=None, choices=["P1", "P2", "P3"])
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-spec", action="store_true")
    parser.add_argument("--spec-id", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = _collect_tasks(root, report=args.report)
    rows = _filter_tasks(rows, project=args.project, task_type=args.type, priority=args.priority, task_id=args.task_id)
    if args.write_spec:
        if len(rows) != 1:
            print(json.dumps({"status": "failed", "error": f"--write-spec requires exactly one selected task, got {len(rows)}"}, ensure_ascii=False, indent=2))
            return 2
        spec_path = _write_spec(root, rows[0], spec_id=args.spec_id, force=args.force)
        print(json.dumps({"status": "created", "spec": spec_path.as_posix(), "task": rows[0]}, ensure_ascii=False, indent=2))
        return 0

    payload = {"status": "ok", "task_count": len(rows), "tasks": rows[: args.limit]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_table(payload["tasks"]))
    return 0


def _collect_tasks(root: Path, *, report: str | None) -> list[dict[str, Any]]:
    paths = [_report_path(root, report)] if report else sorted((root / "artifacts" / "goals" / "reports").glob("goal_*.json"))
    rows = []
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        project = _project_label(data)
        tasks = dict(data.get("analysis_tasks") or {}).get("tasks", [])
        for task in tasks if isinstance(tasks, list) else []:
            if not isinstance(task, dict):
                continue
            row = dict(task)
            row["goal_id"] = data.get("goal_id")
            row["goal"] = data.get("goal")
            row["project"] = project
            row["report_path"] = path.as_posix()
            rows.append(row)
    rows.sort(key=lambda item: (_priority_rank(item.get("priority")), str(item.get("type")), str(item.get("target"))))
    return rows


def _filter_tasks(
    rows: list[dict[str, Any]],
    *,
    project: str | None,
    task_type: str | None,
    priority: str | None,
    task_id: str | None,
) -> list[dict[str, Any]]:
    if project:
        needle = project.lower()
        rows = [row for row in rows if needle in str(row.get("project") or row.get("goal") or "").lower()]
    if task_type:
        rows = [row for row in rows if row.get("type") == task_type]
    if priority:
        rows = [row for row in rows if row.get("priority") == priority]
    if task_id:
        rows = [row for row in rows if row.get("task_id") == task_id]
    return rows


def _write_spec(root: Path, task: dict[str, Any], *, spec_id: str | None, force: bool) -> Path:
    final_id = spec_id or _default_spec_id(task)
    if not _SPEC_ID_RE.match(final_id):
        raise SystemExit("spec id must match ^[a-z][a-z0-9_]*$")
    path = root / "generated" / "specs" / f"{final_id}.json"
    if path.exists() and not force:
        raise SystemExit(f"spec already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = {
        "id": final_id,
        "purpose": f"{task.get('title')}. Target: {task.get('target')}",
        "input_contract": {"value": "string"},
        "output_contract": {"value": "string"},
        "error_policy": {"invalid_input": "raise ValueError"},
        "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
        "quality_gate": {"sample_input": {"value": "hello"}, "expected_output": {"value": "hello"}},
        "reusable": True,
        "source_analysis_task": {
            "task_id": task.get("task_id"),
            "type": task.get("type"),
            "target": task.get("target"),
            "priority": task.get("priority"),
            "acceptance": task.get("acceptance"),
            "report_path": task.get("report_path"),
        },
    }
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _default_spec_id(task: dict[str, Any]) -> str:
    raw = f"{task.get('type', 'analysis')}_{task.get('target', '')}".lower()
    raw = raw.replace(".py", "").replace("/", "_").replace("\\", "_").replace(":", "_")
    raw = re.sub(r"[^a-z0-9_]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw or not raw[0].isalpha():
        raw = f"analysis_{raw}"
    return raw[:80]


def _report_path(root: Path, report: str) -> Path:
    path = Path(report)
    return path if path.is_absolute() else root / path


def _project_label(report: dict[str, Any]) -> str:
    root_input = report.get("root_input")
    if isinstance(root_input, dict) and root_input.get("path"):
        return str(root_input["path"])
    goal = str(report.get("goal") or "")
    marker = "Analyze project "
    if goal.startswith(marker):
        return goal[len(marker) :]
    return goal


def _priority_rank(value: Any) -> int:
    return {"P1": 0, "P2": 1, "P3": 2}.get(str(value), 9)


def _table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No analysis tasks found."
    lines = ["priority type target task_id report"]
    for row in rows:
        lines.append(
            " ".join(
                [
                    str(row.get("priority") or "-"),
                    str(row.get("type") or "-"),
                    str(row.get("target") or "-"),
                    str(row.get("task_id") or "-"),
                    Path(str(row.get("report_path") or "")).name,
                ]
            )
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
