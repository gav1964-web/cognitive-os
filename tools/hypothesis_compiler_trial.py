"""Trial compiled hypotheses through existing gates and plugin foundry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.hypothesis_compiler_trial import run_compiled_hypothesis_trials


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--compilation", default="artifacts/hypothesis_compiler/corpus_compilation.json")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--hypothesis-id", action="append", default=[])
    parser.add_argument("--candidate-type", action="append", default=[])
    parser.add_argument("--maximum-promotions", type=int, default=1)
    parser.add_argument("--maximum-holdouts", type=int, default=3)
    parser.add_argument("--case-timeout", type=float, default=30)
    parser.add_argument("--total-timeout", type=float, default=180)
    parser.add_argument("--timeout-retry-multiplier", type=float, action="append")
    parser.add_argument("--retry-quarantined", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    compilation = Path(args.compilation)
    if not compilation.is_absolute():
        compilation = root / compilation
    report = run_compiled_hypothesis_trials(
        root=root, compilation_path=compilation, promote=args.promote,
        maximum_promotions=max(0, args.maximum_promotions),
        maximum_holdouts_per_hypothesis=max(1, args.maximum_holdouts),
        case_timeout_seconds=max(0.1, args.case_timeout),
        total_timeout_seconds=max(0.1, args.total_timeout),
        hypothesis_ids=set(args.hypothesis_id) or None,
        candidate_types=set(args.candidate_type) or None,
        timeout_retry_multipliers=(
            tuple(args.timeout_retry_multiplier)
            if args.timeout_retry_multiplier is not None else None
        ),
        retry_quarantined=args.retry_quarantined,
        write=not args.no_write,
        progress=lambda event: print(json.dumps(event, ensure_ascii=False), file=sys.stderr, flush=True),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
