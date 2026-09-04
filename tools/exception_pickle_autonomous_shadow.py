"""Run one exception pickle autonomous shadow pass."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.exception_pickle_autonomous_shadow import run_exception_pickle_autonomous_shadow


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--ledger",
        default="artifacts/project_development/supervised_exception_pickle_transfer_ledger.json",
    )
    parser.add_argument(
        "--audit",
        default="artifacts/project_development/exception_pickle_candidate_audit_20260831T120556188729Z.json",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = run_exception_pickle_autonomous_shadow(
        root=root,
        execution_dir=root / "artifacts" / "project_development" / "autonomous_shadow" / stamp,
        ledger_path=Path(args.ledger),
        audit_path=Path(args.audit),
    )
    if args.write:
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"exception_pickle_autonomous_shadow_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"shadow_verified", "autonomous_verified_shadow"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
