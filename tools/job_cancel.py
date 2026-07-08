"""Cancel a durable queue job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True, help="Job id")
    parser.add_argument("--reason", default="manual_cancel")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.durable_queue import DurableQueue

    queue = DurableQueue(root)
    queue.cancel(args.id, reason=args.reason)
    print(json.dumps({"status": "cancelled", "job_id": args.id}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
