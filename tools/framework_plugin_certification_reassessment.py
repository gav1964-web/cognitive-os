from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.framework_plugin_certification_reassessment import (
    build_framework_plugin_certification_reassessment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--prior-certificate-receipt", required=True)
    parser.add_argument("--holdout-reassessment", required=True)
    parser.add_argument("--role-regression", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = build_framework_plugin_certification_reassessment(
        root=root,
        prior_certificate_receipt=args.prior_certificate_receipt,
        holdout_reassessment=_read(root, args.holdout_reassessment),
        role_regression=_read(root, args.role_regression),
    )
    target = root / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "revoked" else 2


def _read(root: Path, value: str) -> dict:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
