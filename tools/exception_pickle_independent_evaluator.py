"""Run independent evaluator review for exception pickle promotion."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_independent_evaluator import review_exception_pickle_promotion


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--readiness",
        default="artifacts/project_development/exception_pickle_promotion_readiness_20260831T124021424040Z.json",
    )
    parser.add_argument(
        "--holdout",
        default="artifacts/project_development/exception_pickle_holdout_transaction_20260831T124242422603Z.json",
    )
    parser.add_argument(
        "--shadow",
        default="artifacts/project_development/exception_pickle_autonomous_shadow_20260831T123815742912Z.json",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = review_exception_pickle_promotion(
        root=root,
        readiness_path=Path(args.readiness),
        holdout_path=Path(args.holdout),
        shadow_path=Path(args.shadow),
    )
    if args.write:
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"exception_pickle_independent_evaluator_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
