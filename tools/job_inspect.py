"""Inspect one durable queue job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True, help="Job id")
    parser.add_argument("--journal-tail", type=int, default=20)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.control_plane import inspect_job

    print(json.dumps(inspect_job(root, args.id, journal_tail=args.journal_tail), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
