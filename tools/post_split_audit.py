"""Run the post-split diagnostic audit."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.post_split_audit import run_post_split_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/project_development/post_split_audit.json")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_post_split_audit(root=root)
    if args.write:
        output = Path(args.output)
        if output.name == "post_split_audit.json":
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = output.with_name(f"post_split_audit_{stamp}.json")
        resolved = output if output.is_absolute() else root / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = resolved.as_posix()
    print(json.dumps(_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "facade_count": report.get("facade_count"),
        "helper_backed_test_count": report.get("helper_backed_test_count"),
        "facade_summary_by_root": report.get("facade_summary_by_root"),
        "recommended_next_actions": report.get("recommended_next_actions"),
        "report_path": report.get("report_path"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
