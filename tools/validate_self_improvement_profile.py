"""Validate a staged semantic profile against independent local projects."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improvement_contract_profile import discover_contract_profile_candidates
from runtime.self_improvement_profile_validation import build_profile_validation_report
from runtime.self_improvement_training import _evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project-dir", action="append", required=True)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    family = str(dict(candidate.get("proposed_record") or {}).get("contract_family") or "")
    observations = []
    for raw in args.project_dir:
        project = Path(raw).resolve()
        discovered = discover_contract_profile_candidates(project)
        matching = [row for row in discovered if dict(row.get("profile") or {}).get("contract_family") == family]
        baseline = _evaluate(root, project, write=True) if matching else None
        observations.append({
            "project": project.name,
            "project_dir": project.as_posix(),
            "recognized_family": family if matching else None,
            "recognized_sources": [row["source"] for row in matching],
            "baseline_score": baseline["project_min_score"] if baseline else None,
            "baseline_role_scores": baseline["role_scores"] if baseline else None,
            "training_status": "already_at_target" if baseline and baseline["project_min_score"] >= args.target_score else "not_run",
            "score_delta": 0.0,
        })
    report = build_profile_validation_report(candidate, observations, target_score=args.target_score)
    if args.write:
        out = root / "artifacts" / "self_improvement"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"profile_validation_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
