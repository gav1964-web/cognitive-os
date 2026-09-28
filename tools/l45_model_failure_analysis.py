"""Analyze failures in model-backed L4.5 semantic comparison reports."""

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

    from runtime.l45_model_failure_analysis import analyze_l45_model_failures, load_json

    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-report")
    parser.add_argument("--comparison-report", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    suite = load_json(Path(args.suite_report)) if args.suite_report else None
    comparisons = [load_json(Path(path)) for path in args.comparison_report]
    out = Path(args.out) if args.out else repo_root / "artifacts" / "l45_semantic_benchmark" / "l45_model_failure_analysis.json"
    report = analyze_l45_model_failures(
        suite_report=suite,
        comparison_reports=comparisons,
        write_path=out if args.write else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
