"""Run the read-only self-development shadow backfill trial."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_development_shadow_trial import run_self_development_shadow_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run_self_development_shadow_trial(
        root=Path(args.root),
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "validated_shadow" else 1


if __name__ == "__main__":
    raise SystemExit(main())
