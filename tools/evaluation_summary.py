from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_summary(root: Path) -> dict[str, Any]:
    evaluation_dir = root / "evaluation"
    rows: list[dict[str, Any]] = []
    verdicts: dict[str, int] = {}
    task_classes: dict[str, int] = {}

    for task_dir in sorted(evaluation_dir.glob("task*")):
        if not task_dir.is_dir() or task_dir.name == "task_template":
            continue
        metrics_path = task_dir / "metrics.json"
        if not metrics_path.exists():
            rows.append({"task_id": task_dir.name, "status": "missing_metrics"})
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        routes = metrics.get("routes", {})
        direct = routes.get("direct_agent", {})
        cognitive = routes.get("cognitive_os", {})
        verdict = str(metrics.get("verdict", "unknown"))
        task_class = str(metrics.get("task_class", "unknown"))
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
        task_classes[task_class] = task_classes.get(task_class, 0) + 1
        rows.append(
            {
                "task_id": metrics.get("task_id", task_dir.name),
                "task_class": task_class,
                "verdict": verdict,
                "direct_status": direct.get("status", "unknown"),
                "cognitive_os_status": cognitive.get("status", "unknown"),
                "winner": metrics.get("comparison", {}).get("winner", "unknown"),
                "confidence": metrics.get("comparison", {}).get("confidence", 0.0),
            }
        )

    return {
        "task_count": len(rows),
        "task_classes": task_classes,
        "verdicts": verdicts,
        "tasks": rows,
    }


def to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Summary",
        "",
        f"- Tasks: `{summary['task_count']}`",
        f"- Classes: `{summary['task_classes']}`",
        f"- Verdicts: `{summary['verdicts']}`",
        "",
        "| Task | Class | Direct | Cognitive OS | Winner | Verdict | Confidence |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in summary["tasks"]:
        lines.append(
            "| `{task_id}` | `{task_class}` | `{direct_status}` | `{cognitive_os_status}` | "
            "`{winner}` | `{verdict}` | `{confidence}` |".format(**row)
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize evaluation corpus metrics.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--write", help="Write Markdown summary to this path.")
    args = parser.parse_args()

    summary = build_summary(Path(args.root))
    if args.json:
        output = json.dumps(summary, indent=2, ensure_ascii=False)
    else:
        output = to_markdown(summary)

    if args.write:
        Path(args.write).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

