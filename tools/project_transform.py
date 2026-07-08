"""Run Project Analyzer extraction through a tested Foundry candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.transformation_flow import run_transformation_flow

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.root).resolve()
    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = workspace / project_dir
    result = run_transformation_flow(
        root=workspace,
        project_dir=project_dir.resolve(),
        force=args.force,
        promote=args.promote,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"promotion_ready", "promoted"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
