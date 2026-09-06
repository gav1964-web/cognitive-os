from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.narrow_type_certification_reassessment import (
    build_narrow_type_certification_reassessment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--certificate-receipt", required=True)
    parser.add_argument("--holdout-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = build_narrow_type_certification_reassessment(
        root=root,
        certificate_receipt=args.certificate_receipt,
        holdout_receipt=args.holdout_receipt,
    )
    target = root / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "revoked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
