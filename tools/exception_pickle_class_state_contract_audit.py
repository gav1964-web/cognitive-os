"""Run class/base-state audit for exception-pickle import-isolation cases."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_class_state_contract_audit import (  # noqa: E402
    DEFAULT_BLOCKER_INTELLIGENCE,
    run_exception_pickle_class_state_contract_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--blocker-intelligence", default=str(DEFAULT_BLOCKER_INTELLIGENCE))
    parser.add_argument("--output", default="artifacts/project_development/exception_pickle_class_state_contract_audit.json")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_class_state_contract_audit(
        root=root,
        blocker_intelligence_path=Path(args.blocker_intelligence),
    )
    if args.write:
        output = Path(args.output)
        if output.name == "exception_pickle_class_state_contract_audit.json":
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = output.with_name(f"exception_pickle_class_state_contract_audit_{stamp}.json")
        resolved = output if output.is_absolute() else root / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = resolved.as_posix()
    print(json.dumps(_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "case_count": report.get("case_count"),
        "research_lane_summary": report.get("research_lane_summary"),
        "missing_import_summary": report.get("missing_import_summary"),
        "recommended_next_lane": report.get("recommended_next_lane"),
        "report_path": report.get("report_path"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
