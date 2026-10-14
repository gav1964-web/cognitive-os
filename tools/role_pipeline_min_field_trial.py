"""Run minimum-based downstream role field trial."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_pipeline_min_field_trial import (
    eligible_projects_from_foundation_report,
    project_classifications_from_foundation_reports,
    run_role_pipeline_min_field_trial,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--foundation-report", action="append", default=[])
    parser.add_argument("--project", action="append", default=[], help="Run only the named project (repeatable)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = (root / args.projects_dir).resolve()
    eligible = None
    foundation_paths = [(root / path).resolve() for path in args.foundation_report]
    if foundation_paths:
        eligible = set().union(*(eligible_projects_from_foundation_report(path) for path in foundation_paths))
    if args.project:
        requested = {str(value) for value in args.project}
        eligible = requested if eligible is None else eligible & requested
    classifications = project_classifications_from_foundation_reports(foundation_paths)
    report = run_role_pipeline_min_field_trial(
        root=root,
        projects_dir=projects_dir,
        eligible_projects=eligible,
        project_classifications=classifications,
        limit=args.limit,
        target_score=args.target_score,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
