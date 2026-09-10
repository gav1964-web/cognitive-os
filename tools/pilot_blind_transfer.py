from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.pilot_transfer_trial import evaluate_pilot_transfer_trial
from runtime.reviewer_adversarial import run_reviewer_adversarial_trial
from tools.github_full_chain_probe import run_probe, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen blind projects through executable pilot transfer")
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--label", default="pilot_blind_full_chain")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    corpus = (root / args.corpus_dir).resolve() if not Path(args.corpus_dir).is_absolute() else Path(args.corpus_dir).resolve()
    selection = json.loads((corpus / "selection.json").read_text(encoding="utf-8"))
    readiness = json.loads(Path(args.readiness_report).read_text(encoding="utf-8"))
    full_chain = run_probe(
        root=root,
        projects_dir=corpus / "src",
        label=args.label,
        run_executor=True,
        run_verification=True,
        checkpoint_path=root / "artifacts" / "field_trials" / f"{args.label}_checkpoint.json",
        resume=args.resume,
        progress=True,
        case_timeout_seconds=300,
    )
    if args.write:
        full_chain.update(write_report(root, full_chain, args.label))
    report = evaluate_pilot_transfer_trial(
        selection=selection,
        full_chain_report=full_chain,
        role_readiness=readiness,
        reviewer_adversarial=run_reviewer_adversarial_trial(root=root),
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["full_chain_report"] = full_chain.get("report_path")
    if args.write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"pilot_transfer_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "eligible" else 1


if __name__ == "__main__":
    raise SystemExit(main())
