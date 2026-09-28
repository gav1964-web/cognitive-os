"""Run prospective shadow detection for systematic Cognitive OS errors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_development_prospective_detection import run_prospective_detection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run_prospective_detection(root=Path(args.root), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"candidate_detected", "waiting_for_evidence"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
