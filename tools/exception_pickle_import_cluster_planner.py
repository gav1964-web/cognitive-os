"""Build an exception-pickle import-isolation cluster plan."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_import_cluster_planner import (
    run_exception_pickle_import_cluster_planner,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--blocker-intelligence")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_import_cluster_planner(
        root=root,
        blocker_intelligence_path=Path(args.blocker_intelligence)
        if args.blocker_intelligence
        else None,
    )
    if args.write:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"exception_pickle_import_cluster_planner_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    output = _summary(report) if args.summary_only else report
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "cluster_count": report.get("cluster_count"),
        "recommended_next_cluster": report.get("recommended_next_cluster"),
        "report_path": report.get("report_path"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
