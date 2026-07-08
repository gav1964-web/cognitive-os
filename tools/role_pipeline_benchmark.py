"""Run the Role Pipeline benchmark suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_pipeline_benchmark import run_role_pipeline_benchmark
from runtime.local_inference import LocalInferenceConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--benchmarks-dir", default="benchmarks/project_analyzer")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--use-architect-llm", action="store_true")
    parser.add_argument("--architect-base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--architect-model", default="local")
    parser.add_argument("--architect-timeout", type=float, default=20.0)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    advisory_config = None
    if args.use_architect_llm:
        advisory_config = LocalInferenceConfig(
            base_url=args.architect_base_url.rstrip("/"),
            model=args.architect_model,
            timeout_seconds=args.architect_timeout,
            provider_label="architect_advisory",
        )
    report = run_role_pipeline_benchmark(
        root,
        benchmarks_dir=(root / args.benchmarks_dir).resolve(),
        write=args.write,
        architect_advisory_config=advisory_config,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
