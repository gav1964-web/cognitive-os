"""Run executable acceptance obligations from a TestPlan artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.executable_acceptance import run_executable_acceptance

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--test-plan", required=True)
    parser.add_argument("--work-dir")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = root / project_dir
    test_plan_path = Path(args.test_plan)
    if not test_plan_path.is_absolute():
        test_plan_path = root / test_plan_path
    work_dir = Path(args.work_dir) if args.work_dir else root / "artifacts" / "executable_acceptance" / "manual"
    if not work_dir.is_absolute():
        work_dir = root / work_dir
    result = run_executable_acceptance(
        root=root,
        project_dir=project_dir.resolve(),
        test_plan=json.loads(test_plan_path.read_text(encoding="utf-8")),
        work_dir=work_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
