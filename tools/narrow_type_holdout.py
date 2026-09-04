from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_holdout_evaluator import evaluate_narrow_type_holdout
from runtime.evidence_ledger import verify_evidence_entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--role-pipeline", required=True)
    parser.add_argument("--stub-audit")
    parser.add_argument("--evaluation-receipt")
    parser.add_argument("--role-pipeline-receipt")
    parser.add_argument("--stub-audit-receipt")
    parser.add_argument("--blind-report-receipt", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    evaluation_path = Path(args.evaluation).resolve()
    stub_audit_path = Path(args.stub_audit).resolve() if args.stub_audit else None
    evaluation = _read(evaluation_path)
    role_pipeline_path = Path(args.role_pipeline).resolve()
    role_pipeline = _read(role_pipeline_path)
    role_pipeline.setdefault("report_path", role_pipeline_path.as_posix())
    stub_audit = _read(stub_audit_path) if stub_audit_path else None
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation,
        role_pipeline_report=role_pipeline,
        stub_audit=stub_audit,
        input_provenance={
            "evaluation": _receipt_provenance(root, evaluation_path, args.evaluation_receipt),
            "role_pipeline": _receipt_provenance(root, role_pipeline_path, args.role_pipeline_receipt),
            "stub_audit": _receipt_provenance(root, stub_audit_path, args.stub_audit_receipt),
            "blind_reports": [
                _receipt_only_provenance(root, value) for value in args.blind_report_receipt
            ],
        },
    )
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
    print(encoded.decode("utf-8"), end="")
    return 0 if report["status"] == "passed" else 2


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_provenance(root: Path, path: Path | None, receipt: str | None) -> dict:
    if path is None or receipt is None:
        return {"verified": False}
    record = _receipt_only_provenance(root, receipt)
    digest = _file_digest(path)
    return {**record, "input_path": path.as_posix(), "input_digest": digest,
            "verified": record.get("verified") is True and record.get("content_digest") == digest}


def _receipt_only_provenance(root: Path, receipt: str) -> dict:
    verification = verify_evidence_entry(root=root, ledger_path=Path(receipt))
    entry = dict(verification.get("entry") or {})
    return {
        "receipt": str(receipt).replace("\\", "/"),
        "entry_digest": entry.get("entry_digest"),
        "content_digest": entry.get("content_sha256"),
        "verified": verification.get("status") == "verified",
    }


if __name__ == "__main__":
    raise SystemExit(main())
