"""Build the prospective baseline/candidate experiment queue."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.self_development_experiment_queue import build_self_development_experiment_queue
from runtime.self_development_prospective_detection import run_prospective_detection


DEFAULT_CERTIFICATION_RECEIPT = (
    "evidence/ledger/ca0bdda72697373d304b9a28923728612da25a58e09b4ad10e07c8f57f6bd657.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--certification-receipt", default=DEFAULT_CERTIFICATION_RECEIPT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    detection = run_prospective_detection(root=root, write=False)
    report = build_self_development_experiment_queue(
        root=root,
        detection=detection,
        certification_receipt=args.certification_receipt,
    )
    if args.write:
        directory = root / "artifacts" / "self_development"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / f"self_development_experiment_queue_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.relative_to(root).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
