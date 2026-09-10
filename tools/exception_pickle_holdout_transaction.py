"""Run read-only exception pickle holdout transaction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.config_doctor import run_config_doctor
from runtime.exception_pickle_holdout_transaction import (
    run_exception_pickle_holdout_transaction,
)
from runtime.project_native_failure_intake import _run_bounded_process


REGRESSION_FILES = [
    "tests/runtime/test_exception_pickle_promotion_readiness.py",
    "tests/runtime/test_exception_pickle_candidate_audit.py",
    "tests/runtime/test_programmer_exception_pickle_patch.py",
    "tests/runtime/test_project_development_authorized_implementation.py",
]


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
    parser.add_argument("--minimum-holdout-candidates", type=int, default=3)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    regression = _run_bounded_process(
        [
            sys.executable,
            "-m",
            "pytest",
            *REGRESSION_FILES,
            "-q",
            "--basetemp=.pytest-tmp-exception-pickle-holdout",
        ],
        cwd=root,
        env=dict(os.environ),
        timeout=180,
    )
    doctor = run_config_doctor(root)
    report = run_exception_pickle_holdout_transaction(
        root=root,
        ledger_path=Path(args.ledger),
        audit_path=Path(args.audit),
        minimum_holdout_candidates=args.minimum_holdout_candidates,
        regression_passed=regression.returncode == 0,
        config_doctor_passed=doctor.get("status") == "ok",
    )
    report["regression_summary"] = "\n".join(regression.stdout.strip().splitlines()[-3:])
    report["config_doctor_summary"] = dict(doctor.get("summary") or {})
    if args.write:
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"exception_pickle_holdout_transaction_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "holdout_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
