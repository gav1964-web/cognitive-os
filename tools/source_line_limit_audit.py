"""Run the repo-level Python source line-limit audit."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.source_line_limit_audit import DEFAULT_LIMIT, run_source_line_limit_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--line-limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default="artifacts/project_development/source_line_limit_audit.json")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--fail-on-violation", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_source_line_limit_audit(root=root, line_limit=args.line_limit)
    if args.write:
        output = Path(args.output)
        if output.name == "source_line_limit_audit.json":
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = output.with_name(f"source_line_limit_audit_{stamp}.json")
        resolved = output if output.is_absolute() else root / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = resolved.as_posix()
    print(json.dumps(_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.fail_on_violation and report["status"] != "passed" else 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "line_limit": report.get("line_limit"),
        "scanned_python_file_count": report.get("scanned_python_file_count"),
        "violation_count": report.get("violation_count"),
        "violation_summary_by_root": report.get("violation_summary_by_root"),
        "top_violations": report.get("top_violations"),
        "report_path": report.get("report_path"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
