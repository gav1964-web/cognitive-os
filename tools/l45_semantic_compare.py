"""Compare deterministic and model-backed L4.5 semantic benchmark reports."""

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

    from runtime.l45_semantic_comparison import compare_l45_semantic_reports, load_report

    parser = argparse.ArgumentParser()
    parser.add_argument("--deterministic-report", required=True)
    parser.add_argument("--model-report", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out = None
    if args.write:
        out = Path(args.out).resolve() if args.out else repo_root / "artifacts" / "l45_semantic_benchmark" / "l45_semantic_comparison.json"
    report = compare_l45_semantic_reports(
        deterministic_report=load_report(Path(args.deterministic_report).resolve()),
        model_report=load_report(Path(args.model_report).resolve()),
        write_path=out,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
