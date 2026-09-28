"""Run bounded Researcher planning field trials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.researcher_min_field_trial import run_researcher_min_field_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--foundation-report", action="append", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = run_researcher_min_field_trial(
        root=root,
        foundation_reports=[(root / path).resolve() for path in args.foundation_report],
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
