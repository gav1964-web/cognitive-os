"""Run ProjectMapReport -> ADR -> TechnicalSpec foundation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.local_inference import LocalInferenceConfig
from runtime.role_foundation_pipeline import run_role_foundation_benchmark, run_role_foundation_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir")
    parser.add_argument("--benchmarks-dir", default="benchmarks/project_analyzer")
    parser.add_argument("--benchmark-project", default=None)
    parser.add_argument("--goal", default="Prepare ADR and TechnicalSpec for first safe transformation")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
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
    if args.benchmark:
        result = run_role_foundation_benchmark(
            root,
            benchmarks_dir=(root / args.benchmarks_dir).resolve(),
            project=args.benchmark_project,
            write=args.write,
            architect_advisory_config=advisory_config,
        )
    else:
        if not args.project_dir:
            print(json.dumps({"status": "failed", "error": "--project-dir is required without --benchmark"}))
            return 2
        project_dir = Path(args.project_dir)
        if not project_dir.is_absolute():
            project_dir = root / project_dir
        result = run_role_foundation_pipeline(
            root=root,
            project_dir=project_dir.resolve(),
            goal=args.goal,
            write=args.write,
            architect_advisory_config=advisory_config,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
