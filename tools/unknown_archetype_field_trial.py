"""Run adversarial unknown-archetype and role-chain field trials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.unknown_archetype_field_trial import run_unknown_archetype_field_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = (root / args.projects_dir).resolve() if args.projects_dir else None
    report = run_unknown_archetype_field_trial(
        root=root,
        projects_dir=projects_dir,
        limit=args.limit,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
