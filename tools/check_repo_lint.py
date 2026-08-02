"""Run repository-level static lint gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-python-lines", type=int, default=400)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.repo_lint import lint_repository

    violations = lint_repository(root, max_python_lines=args.max_python_lines)
    payload = {
        "status": "ok" if not violations else "failed",
        "max_python_lines": args.max_python_lines,
        "violations": [item.to_dict() for item in violations],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
