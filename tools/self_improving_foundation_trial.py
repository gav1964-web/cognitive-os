"""Run a bounded self-improvement loop over a foundation-role corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial
from tools.self_improvement_project_discovery import holdout_discoverer


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", action="append", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--max-training-projects", type=int, default=3)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--regression-case-count", type=int, default=3)
    promotion = parser.add_mutually_exclusive_group()
    promotion.add_argument("--promote-config", dest="promote_config", action="store_true")
    promotion.add_argument("--no-promote-config", dest="promote_config", action="store_false")
    parser.set_defaults(promote_config=None)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--no-executable-acceptance", action="store_true")
    parser.add_argument("--no-hypothesis-discovery", action="store_true")
    parser.add_argument("--full-report", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_roots = [_resolve(root, value) for value in args.projects_dir]
    report = run_self_improving_foundation_trial(
        root=root,
        project_roots=project_roots,
        limit=args.limit,
        target_score=args.target_score,
        max_training_projects=args.max_training_projects,
        max_iterations=args.max_iterations,
        regression_case_count=args.regression_case_count,
        promote_config=args.promote_config,
        write=not args.no_write,
        executable_acceptance=not args.no_executable_acceptance,
        _holdout_discoverer=(
            None if args.no_hypothesis_discovery or args.no_write
            else holdout_discoverer(root)
        ),
        _progress=_progress,
    )
    output = report if args.full_report else _summary(report)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "target_verified" else 1


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _progress(event: dict[str, object]) -> None:
    payload = {"self_improvement_progress": event}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


def _summary(report: dict[str, object]) -> dict[str, object]:
    critical = dict(report.get("critical_intervention") or {})
    return {
        "artifact_type": report.get("artifact_type"),
        "status": report.get("status"),
        "report_path": report.get("report_path"),
        "summary": report.get("summary"),
        "critical_intervention": critical,
        "capability_development_requests": report.get("capability_development_requests", []),
    }


if __name__ == "__main__":
    raise SystemExit(main())
