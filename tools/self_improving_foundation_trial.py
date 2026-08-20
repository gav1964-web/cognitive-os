"""Run a bounded self-improvement loop over a foundation-role corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", action="append", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--max-training-projects", type=int, default=3)
    parser.add_argument("--regression-case-count", type=int, default=3)
    promotion = parser.add_mutually_exclusive_group()
    promotion.add_argument("--promote-config", dest="promote_config", action="store_true")
    promotion.add_argument("--no-promote-config", dest="promote_config", action="store_false")
    parser.set_defaults(promote_config=None)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--no-executable-acceptance", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_roots = [_resolve(root, value) for value in args.projects_dir]
    report = run_self_improving_foundation_trial(
        root=root,
        project_roots=project_roots,
        limit=args.limit,
        target_score=args.target_score,
        max_training_projects=args.max_training_projects,
        regression_case_count=args.regression_case_count,
        promote_config=args.promote_config,
        write=not args.no_write,
        executable_acceptance=not args.no_executable_acceptance,
        _progress=_progress,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "target_verified" else 1


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _progress(event: dict[str, object]) -> None:
    payload = {"self_improvement_progress": event}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
