"""Generate L4.5 risk-policy gap reports from benchmark output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.l45_semantic_analytics import build_l45_risk_policy_gap_report

    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    out_path = Path(args.out) if args.out else report_path.with_name(report_path.stem + "_policy_gap.json")
    gap_report = build_l45_risk_policy_gap_report(report, write_path=out_path if args.write else None)
    print(json.dumps(gap_report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if gap_report.get("status") in {"ok", "gaps_found"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
