"""Archive or remove durable queue terminal jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--archive-terminal", action="store_true")
    parser.add_argument("--delete-archive", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.durable_queue import DurableQueue

    queue = DurableQueue(root)
    result: dict[str, object] = {"status": "ok"}
    if args.archive_terminal:
        result["archived"] = queue.archive_terminal()
    if args.delete_archive:
        result["removed"] = queue.cleanup_archived()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
