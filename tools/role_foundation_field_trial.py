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
        required=True,
        help="Directory with Python projects; if it contains a projects/ child, that child is used as corpus.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--target-score", type=float, default=9.2)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_roots = []
    for item in args.projects_dir:
        path = Path(item)
        if not path.is_absolute():
            path = root / path
        project_roots.append(path.resolve())
    report = run_role_foundation_field_trial(
        root=root,
        project_roots=project_roots,
        limit=args.limit,
        write=args.write,
        target_score=args.target_score,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
