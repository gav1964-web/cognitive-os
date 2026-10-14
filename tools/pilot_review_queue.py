from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.pilot_operations import build_pilot_review_queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact human pilot review queue")
    parser.add_argument("--root", default=".")
    parser.add_argument("--run-record", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    records = []
    for value in args.run_record:
        path = Path(value)
        path = path.resolve() if path.is_absolute() else (root / path).resolve()
        records.append(json.loads(path.read_text(encoding="utf-8")))
    report = build_pilot_review_queue(records)
    if args.write:
        out = root / "artifacts" / "pilot"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"pilot_review_queue_{stamp}.json"
        report["report_path"] = path.as_posix()
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
