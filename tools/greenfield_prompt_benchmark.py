"""Run greenfield Architect -> SpecWriter prompt benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.greenfield_prompt_benchmark import run_greenfield_prompt_benchmark

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--benchmark", default="benchmarks/greenfield_prompts/cases.json")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.root).resolve()
    benchmark = Path(args.benchmark)
    if not benchmark.is_absolute():
        benchmark = workspace / benchmark
    report = run_greenfield_prompt_benchmark(root=workspace, benchmark_path=benchmark, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
