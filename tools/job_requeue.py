"""Requeue stale running jobs or one specific job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", default=None, help="Specific running job id to requeue")
    parser.add_argument("--older-than-seconds", type=float, default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.durable_queue import DurableQueue

    queue = DurableQueue(root)
    if args.id:
        requeued = [args.id] if queue.requeue(args.id) else []
    else:
        requeued = queue.requeue_stale_running(older_than_seconds=args.older_than_seconds)
    print(json.dumps({"status": "ok", "requeued": requeued}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
