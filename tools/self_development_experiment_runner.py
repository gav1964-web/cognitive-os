"""Run a receipt-bound baseline/candidate self-development comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_development_experiment_runner import run_baseline_candidate_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--candidate-digest", required=True)
    parser.add_argument("--baseline-receipt", required=True)
    parser.add_argument("--candidate-receipt", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    queue = json.loads((root / args.queue).read_text(encoding="utf-8"))
    result = run_baseline_candidate_experiment(
        root=root,
        queue=queue,
        candidate_digest=args.candidate_digest,
        baseline_receipt=args.baseline_receipt,
        candidate_receipt=args.candidate_receipt,
        write=args.write,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"comparison_ready", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
