from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.pilot_operations import build_pilot_run_record
from runtime.pilot_profile import load_pilot_profile
from runtime.reviewer_adversarial import run_reviewer_adversarial_trial
from tools.github_full_chain_probe import run_probe, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a source-clean supervised pilot batch")
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--transfer-report", required=True)
    parser.add_argument("--label", default="pilot_supervised")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects = _resolve(root, args.projects_dir)
    readiness = json.loads(_resolve(root, args.readiness_report).read_text(encoding="utf-8"))
    transfer_path = _resolve(root, args.transfer_report)
    transfer = json.loads(transfer_path.read_text(encoding="utf-8"))
    transfer.setdefault("report_path", transfer_path.as_posix())
    profile = load_pilot_profile()
    full_chain = run_probe(
        root=root,
        projects_dir=projects,
        label=args.label,
        run_executor=True,
        run_verification=True,
        checkpoint_path=root / "artifacts" / "field_trials" / f"{args.label}_checkpoint.json",
        resume=False,
        progress=True,
        case_timeout_seconds=300,
        recognition_profile=profile,
        stop_outside_recognition_profile=True,
    )
    if args.write:
        full_chain.update(write_report(root, full_chain, args.label))
    adversarial = run_reviewer_adversarial_trial(root=root)
    records = []
    for case in full_chain.get("cases") or []:
        scoped = {**full_chain, "cases": [case]}
        record = build_pilot_run_record(
            full_chain_report=scoped,
            transfer_report=transfer,
            role_readiness=readiness,
            reviewer_adversarial=adversarial,
            profile=profile,
        )
        if args.write:
            path = _artifact_path(root, "pilot_run", str(record["run_id"]))
            record["report_path"] = path.as_posix()
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        records.append(record)
    batch = {
        "artifact_type": "PilotRunBatchReport",
        "schema_version": "pilot_run_batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_human_review" if records else "controlled_stop",
        "run_count": len(records),
        "records": records,
        "safety": {"source_apply_allowed": False, "automatic_approval_allowed": False},
    }
    if args.write:
        path = _artifact_path(root, "pilot_run_batch")
        batch["report_path"] = path.as_posix()
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if records else 1


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _artifact_path(root: Path, prefix: str, identity: str = "") -> Path:
    out = root / "artifacts" / "pilot"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    suffix = f"_{identity}" if identity else ""
    return out / f"{prefix}_{stamp}{suffix}.json"


if __name__ == "__main__":
    raise SystemExit(main())
