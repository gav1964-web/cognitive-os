"""Shadow-test and optionally promote one Cognitive OS config mutation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_improvement_evolution_runner import evolve_foundation_policy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--regression-project-dir", action="append", default=[])
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    def project(value: str) -> Path:
        path = Path(value)
        return (path if path.is_absolute() else root / path).resolve()

    proposal = json.loads(project(args.proposal).read_text(encoding="utf-8"))
    report = evolve_foundation_policy(
        root=root,
        project_dir=project(args.project_dir),
        regression_projects=[project(value) for value in args.regression_project_dir],
        proposal=proposal,
        target_score=args.target_score,
        promote=args.promote,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
