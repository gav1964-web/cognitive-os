from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_development_boundary_field_trial import run_boundary_field_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path)
    parser.add_argument("--split", choices=["train", "blind"])
    args = parser.parse_args()
    report = run_boundary_field_trial(args.corpus_dir, split=args.split)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
