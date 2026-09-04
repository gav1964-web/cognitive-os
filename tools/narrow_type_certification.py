from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_certification import build_narrow_type_certification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--holdout-receipt", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    evaluation = json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    certificate = build_narrow_type_certification(
        evaluation=evaluation,
        evidence_root=root,
        holdout_receipt=args.holdout_receipt,
    )
    encoded = json.dumps(certificate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if certificate["status"] == "certified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
