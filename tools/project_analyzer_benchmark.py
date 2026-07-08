"""Run the Project Analyzer benchmark suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_benchmark import run_benchmark_suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--benchmarks-dir", default="benchmarks/project_analyzer")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    benchmarks_dir = (root / args.benchmarks_dir).resolve()
    report = run_benchmark_suite(root, benchmarks_dir=benchmarks_dir, write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
