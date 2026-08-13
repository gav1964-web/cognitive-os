"""Train Cognitive OS on one project that falls below its target score."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improvement_training import train_on_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="do not persist the training report or KB candidate; verified role evidence is still written",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    project = Path(args.project_dir)
    if not project.is_absolute():
        project = root / project
    report = train_on_project(
        root=root,
        project_dir=project.resolve(),
        target_score=args.target_score,
        write=not args.no_write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"already_at_target", "confirmed_improvement"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
