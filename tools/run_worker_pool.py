"""Run durable queue workers until the queue is idle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-jobs", type=int, default=None)
    parser.add_argument("--loop-cycles", type=int, default=None, help="Run daemon-like bounded loop cycles")
    parser.add_argument("--idle-sleep", type=float, default=1.0)
    parser.add_argument("--lease-seconds", type=float, default=30.0)
    parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    parser.add_argument("--requeue-stale-seconds", type=float, default=None)
    parser.add_argument("--allow-in-process", action="store_true", help="Do not force process boundary in workers")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.worker_pool import WorkerPool

    result = WorkerPool(
        root,
        max_workers=args.workers,
        force_process_boundary=not args.allow_in_process,
        lease_seconds=args.lease_seconds,
        heartbeat_interval_seconds=args.heartbeat_interval,
    )
    if args.loop_cycles is None:
        payload = result.run_until_idle(max_jobs=args.max_jobs)
    else:
        payload = result.run_loop(
            max_cycles=args.loop_cycles,
            idle_sleep_seconds=args.idle_sleep,
            max_jobs_per_cycle=args.max_jobs,
            stale_lease_seconds=args.requeue_stale_seconds,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
