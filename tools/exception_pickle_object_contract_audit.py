"""Run source-backed object contract audit for exception-pickle materializers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_object_contract_audit import (  # noqa: E402
    DEFAULT_OBJECT_CONTRACT_AUDIT,
    run_exception_pickle_object_contract_audit,
)
from runtime.local_inference import LocalInferenceConfig  # noqa: E402


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
    parser.add_argument("--output", default=str(DEFAULT_OBJECT_CONTRACT_AUDIT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--use-l45-llm", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_exception_pickle_object_contract_audit(
        root=root,
        audit_path=Path(args.audit),
        application_ledger_path=Path(args.application_ledger),
        advisory_config=LocalInferenceConfig.from_l45_env() if args.use_l45_llm else None,
    )
    if args.write:
        output = Path(args.output)
        if output == DEFAULT_OBJECT_CONTRACT_AUDIT:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output = output.with_name(f"exception_pickle_object_contract_audit_{stamp}.json")
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
        "case_count": report.get("case_count"),
        "contract_summary": report.get("contract_summary"),
        "advisory_summary": report.get("advisory_summary"),
        "report_path": report.get("report_path"),
        "llm_advisory_allowed": report.get("llm_advisory_allowed"),
        "llm_authority": report.get("llm_authority"),
        "source_apply": report.get("source_apply"),
        "kb_promotion": report.get("kb_promotion"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
