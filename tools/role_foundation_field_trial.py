"""Run minimum-based foundation field trial over Python projects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_foundation_field_trial import run_role_foundation_field_trial


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--projects-dir",
        action="append",
        default=[],
        help="Directory with Python projects; if it contains a projects/ child, that child is used as corpus.",
    )
    parser.add_argument(
        "--exact-project-dir",
        action="append",
        default=[],
        help="Run the directory itself as one case, without child-project discovery.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--target-score", type=float, default=9.2)
    parser.add_argument("--case-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--executable-acceptance", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_roots = []
    for item in args.projects_dir:
        path = Path(item)
        if not path.is_absolute():
            path = root / path
        project_roots.append(path.resolve())
    exact_project_roots = []
    for item in args.exact_project_dir:
        path = Path(item)
        if not path.is_absolute():
            path = root / path
        exact_project_roots.append(path.resolve())
    if not project_roots and not exact_project_roots:
        parser.error("at least one --projects-dir or --exact-project-dir is required")
    report = run_role_foundation_field_trial(
        root=root,
        project_roots=project_roots,
        exact_project_roots=exact_project_roots or None,
        limit=args.limit,
        write=args.write,
        target_score=args.target_score,
        executable_acceptance=args.executable_acceptance,
        case_timeout_seconds=args.case_timeout_seconds,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
