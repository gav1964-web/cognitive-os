from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.pilot_profile import evaluate_pilot_candidate
from runtime.reviewer_adversarial import run_reviewer_adversarial_trial


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the bounded Cognitive OS pilot gate")
    parser.add_argument("--root", default=".")
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--project-stratum", default="library_pure_transform")
    parser.add_argument("--risk-profile", action="append", default=["deterministic"])
    parser.add_argument("--effect-mode", default="pure")
    parser.add_argument("--requested-mode", default="sandbox_patch")
    parser.add_argument("--blind-projects", type=int, default=0)
    parser.add_argument("--independent-lineages", type=int, default=0)
    parser.add_argument("--handoff-loss", type=int, default=0)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    readiness = json.loads(Path(args.readiness_report).read_text(encoding="utf-8"))
    adversarial = run_reviewer_adversarial_trial(root=root)
    report = evaluate_pilot_candidate(
        project_stratum=args.project_stratum,
        risk_profiles=args.risk_profile,
        effect_mode=args.effect_mode,
        requested_mode=args.requested_mode,
        role_readiness=readiness,
        transfer_evidence={
            "blind_projects": args.blind_projects,
            "independent_lineages": args.independent_lineages,
            "handoff_loss": args.handoff_loss,
        },
        reviewer_adversarial=adversarial,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    if args.write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"pilot_admission_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"eligible", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
