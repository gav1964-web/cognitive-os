"""Run admission for source-backed exception object contracts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_object_contract_admission import (  # noqa: E402
    DEFAULT_OBJECT_CONTRACT_ADMISSION,
    run_exception_pickle_object_contract_admission,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--object-contract-audit", required=True)
    parser.add_argument("--minimum-confidence", type=float, default=0.7)
    parser.add_argument("--output", default=str(DEFAULT_OBJECT_CONTRACT_ADMISSION))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_object_contract_admission(
        root=root,
        object_contract_audit_path=Path(args.object_contract_audit),
        minimum_confidence=args.minimum_confidence,
    )
    if args.write:
        output = Path(args.output)
        if output == DEFAULT_OBJECT_CONTRACT_ADMISSION:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = output.with_name(f"exception_pickle_object_contract_admission_{stamp}.json")
        resolved = output if output.is_absolute() else root / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = resolved.as_posix()
    payload = _summary(report) if args.summary_only else report
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "admitted_case_count": report.get("admitted_case_count"),
        "held_case_count": report.get("held_case_count"),
        "admitted_contract_summary": report.get("admitted_contract_summary"),
        "held_contract_summary": report.get("held_contract_summary"),
        "report_path": report.get("report_path"),
        "llm_authority": report.get("llm_authority"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
