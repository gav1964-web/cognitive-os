from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.reviewer_adversarial import run_reviewer_adversarial_trial


def main() -> int:
    parser = argparse.ArgumentParser(description="Run adversarial artifact mutations against Reviewer")
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run_reviewer_adversarial_trial(root=Path(args.root).resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
