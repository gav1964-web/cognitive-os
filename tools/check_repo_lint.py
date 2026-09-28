"""Run repository-level static lint gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--phase", choices=["development", "final"], default="final")
    parser.add_argument("--max-python-lines", type=int, default=400)
    parser.add_argument("--warn-python-lines", type=int, default=350)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.repo_lint import lint_repository, size_warnings

    if not 1 <= args.warn_python_lines <= args.max_python_lines:
        parser.error("warning threshold must be between 1 and the hard limit")

    violations = lint_repository(root, max_python_lines=args.max_python_lines)
    payload = {
        "status": "ok" if not violations or args.phase == "development" else "failed",
        "phase": args.phase,
        "stage_complete": not violations,
        "max_python_lines": args.max_python_lines,
        "violations": [item.to_dict() for item in violations],
        "warning_threshold": args.warn_python_lines,
        "warnings": [item.to_dict() for item in size_warnings(
            root, warning_lines=args.warn_python_lines, max_python_lines=args.max_python_lines)],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not violations or args.phase == "development" else 1


if __name__ == "__main__":
    raise SystemExit(main())
