"""Build an exception-pickle failed-probe diagnosis report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_failed_probe_analyzer import (
    run_exception_pickle_failed_probe_analyzer,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--audit", default="artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json")
    parser.add_argument("--application-ledger", default="artifacts/project_development/exception_pickle_active_application_ledger.json")
    parser.add_argument("--object-contract-admission")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_failed_probe_analyzer(
        root=root,
        audit_path=Path(args.audit),
        application_ledger_path=Path(args.application_ledger),
        object_contract_admission_path=Path(args.object_contract_admission)
        if args.object_contract_admission
        else None,
    )
    if args.write:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"exception_pickle_failed_probe_analyzer_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    output = _summary(report) if args.summary_only else report
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "failed_probe_case_count": report.get("failed_probe_case_count"),
        "blocker_summary": report.get("blocker_summary"),
        "failure_subtype_summary": report.get("failure_subtype_summary"),
        "repair_lane_summary": report.get("repair_lane_summary"),
        "recommended_next_repair_lane": report.get("recommended_next_repair_lane"),
        "report_path": report.get("report_path"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
