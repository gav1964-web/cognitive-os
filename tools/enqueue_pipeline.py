"""Enqueue a Pipeline DSL run into the durable queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--pipeline", required=True, help="Pipeline JSON path relative to root or absolute")
    parser.add_argument("--input-json", required=True, help="Root input JSON object")
    parser.add_argument("--reset-registry", action="store_true")
    parser.add_argument("--priority", type=int, default=100, help="Lower number means earlier claim")
    parser.add_argument("--max-attempts", type=int, default=3, help="Job-level attempts before terminal failure")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.durable_queue import DurableQueue
    from runtime.pipeline import load_pipeline

    pipeline_path = Path(args.pipeline)
    if not pipeline_path.is_absolute():
        pipeline_path = root / pipeline_path
    root_input = json.loads(args.input_json)
    if not isinstance(root_input, dict):
        raise SystemExit("--input-json must decode to an object")
    job_id = DurableQueue(root).enqueue(
        load_pipeline(pipeline_path),
        root_input,
        reset_registry=bool(args.reset_registry),
        priority=args.priority,
        max_attempts=args.max_attempts,
    )
    print(json.dumps({"status": "queued", "job_id": job_id}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
