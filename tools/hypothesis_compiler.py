"""Compile the existing Cognitive OS evidence corpus into reusable hypotheses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.local_inference import LocalInferenceConfig
from runtime.self_improvement_hypothesis_compiler import compile_existing_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=2500)
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument("--model-limit", type=int, default=0)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = compile_existing_evidence(
        root=Path(args.root).resolve(), limit=max(0, args.limit),
        write=not args.no_write, use_model=args.use_model,
        model_limit=max(0, args.model_limit),
        model_config=LocalInferenceConfig.from_env() if args.use_model else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"compiled", "no_eligible_clusters"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
