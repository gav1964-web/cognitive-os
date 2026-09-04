"""Build a read-only blocker intelligence report for exception-pickle work."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_blocker_intelligence import (
    run_exception_pickle_blocker_intelligence,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--audit",
        default="artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json",
    )
    parser.add_argument(
        "--application-ledger",
        default="artifacts/project_development/exception_pickle_active_application_ledger.json",
    )
    parser.add_argument("--object-contract-admission")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_blocker_intelligence(
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
        path = out / f"exception_pickle_blocker_intelligence_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    print(json.dumps(_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "blocked_case_count": report.get("blocked_case_count"),
        "blocker_summary": report.get("blocker_summary"),
        "next_operator_lane_summary": report.get("next_operator_lane_summary"),
        "recommended_next_operator": report.get("recommended_next_operator"),
        "recommended_sequence": report.get("recommended_sequence"),
        "report_path": report.get("report_path"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
