"""Generate a real programmer project and ask tester for an opinion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.programmer_project_review import run_programmer_project_review

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--curriculum-dir", default="curricula/programmer_prompt_local_10")
    parser.add_argument("--case", default="json_log_filter_cli")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = Path(args.curriculum_dir)
    if not curriculum_dir.is_absolute():
        curriculum_dir = root / curriculum_dir
    report = run_programmer_project_review(
        root=root,
        curriculum_dir=curriculum_dir,
        case_name=args.case,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
