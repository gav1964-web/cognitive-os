"""Find reproducible, target-bound failures in isolated project copies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_native_failure_intake import run_project_native_failure_intake


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project", action="append", required=True)
    parser.add_argument(
        "--test-target",
        action="append",
        default=[],
        help="Project-relative pytest nodeid to reproduce; may be repeated.",
    )
    parser.add_argument(
        "--stratum",
        required=True,
        choices=["cli_local_tool", "library_pure_transform", "framework_plugin_build"],
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects = [((root / value) if not Path(value).is_absolute() else Path(value)).resolve() for value in args.project]
    report = run_project_native_failure_intake(
        root=root,
        projects=projects,
        project_stratum=args.stratum,
        test_targets=args.test_target,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
