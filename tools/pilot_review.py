from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.pilot_operations import review_pilot_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a digest-bound human pilot decision")
    parser.add_argument("--root", default=".")
    parser.add_argument("--run-record", required=True)
    parser.add_argument("--decision", required=True, choices=("approve", "rework", "stop"))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source = Path(args.run_record)
    source = source.resolve() if source.is_absolute() else (root / source).resolve()
    record = json.loads(source.read_text(encoding="utf-8"))
    reviewed = review_pilot_run(
        record, decision=args.decision, reviewer=args.reviewer, note=args.note
    )
    reviewed["reviewed_record_source"] = source.as_posix()
    if args.write:
        out = root / "artifacts" / "pilot"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"pilot_reviewed_run_{stamp}.json"
        reviewed["review_report_path"] = path.as_posix()
        path.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(reviewed, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
