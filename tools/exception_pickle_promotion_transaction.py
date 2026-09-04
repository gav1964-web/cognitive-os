"""Run manual promotion transaction for exception pickle reconstruction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.config_doctor import run_config_doctor
from runtime.exception_pickle_promotion_transaction import (
    promote_exception_pickle_reconstruction,
)
from runtime.project_native_failure_intake import _run_bounded_process


REGRESSION_FILES = [
    "tests/runtime/test_exception_pickle_holdout_transaction.py",
    "tests/runtime/test_exception_pickle_autonomous_shadow.py",
    "tests/runtime/test_exception_pickle_promotion_readiness.py",
    "tests/runtime/test_exception_pickle_independent_evaluator.py",
    "tests/runtime/test_exception_pickle_promotion_transaction.py",
    "tests/runtime/test_project_development_authorized_implementation.py",
    "tests/runtime/test_exception_pickle_candidate_audit.py",
    "tests/runtime/test_programmer_exception_pickle_patch.py",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--readiness",
        default="artifacts/project_development/exception_pickle_promotion_readiness_20260831T124021424040Z.json",
    )
    parser.add_argument("--evaluator", required=True)
    parser.add_argument(
        "--holdout",
        default="artifacts/project_development/exception_pickle_holdout_transaction_20260831T124242422603Z.json",
    )
    parser.add_argument(
        "--catalog",
        default="knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json",
    )
    parser.add_argument("--approve", action="store_true")
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
            "--basetemp=.pytest-tmp-exception-pickle-promotion-transaction",
        ],
        cwd=root,
        env=dict(os.environ),
        timeout=180,
    )
    doctor = run_config_doctor(root)
    report = promote_exception_pickle_reconstruction(
        root=root,
        readiness_path=Path(args.readiness),
        evaluator_review_path=Path(args.evaluator),
        holdout_path=Path(args.holdout),
        explicit_approval=args.approve,
        regression_passed=regression.returncode == 0,
        config_doctor_passed=doctor.get("status") == "ok",
        catalog_path=Path(args.catalog),
    )
    report["regression_summary"] = _tail(regression.stdout)
    report["config_doctor_summary"] = dict(doctor.get("summary") or {})
    if args.write:
        out = root / "artifacts" / "project_development"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"exception_pickle_promotion_transaction_{stamp}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "promoted" else 2


def _tail(output: str) -> str:
    return "\n".join(output.strip().splitlines()[-3:])


if __name__ == "__main__":
    raise SystemExit(main())
