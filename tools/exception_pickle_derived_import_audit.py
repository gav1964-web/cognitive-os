from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_derived_import_audit import (
    DEFAULT_AUDIT,
    DEFAULT_DERIVED_AUDIT,
    run_exception_pickle_derived_import_audit,
    write_exception_pickle_derived_import_audit,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--derived-message-audit", type=Path, default=DEFAULT_DERIVED_AUDIT)
    parser.add_argument("--candidate-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    report = (
        write_exception_pickle_derived_import_audit(
            root=root,
            derived_message_audit_path=args.derived_message_audit,
            candidate_audit_path=args.candidate_audit,
        )
        if args.write
        else run_exception_pickle_derived_import_audit(
            root=root,
            derived_message_audit_path=args.derived_message_audit,
            candidate_audit_path=args.candidate_audit,
        )
    )
    if args.summary_only:
        report = {
            "status": report.get("status"),
            "case_count": report.get("case_count"),
            "lane_summary": report.get("lane_summary"),
            "recommended_next_lane": report.get("recommended_next_lane"),
            "report_path": report.get("report_path"),
            "source_apply": report.get("source_apply"),
            "kb_promotion": report.get("kb_promotion"),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
