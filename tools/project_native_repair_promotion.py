"""Run explicit no-regression promotion for project-native repair patterns."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.config_doctor import run_config_doctor
from runtime.project_native_failure_intake import _run_bounded_process
from runtime.project_native_repair_promotion import promote_native_repair_patterns


REGRESSION_FILES = [
    "tests/runtime/test_programmer_falsy_empty_patch.py",
    "tests/runtime/test_programmer_registry_fallback_patch.py",
    "tests/runtime/test_programmer_timestamp_range_patch.py",
    "tests/runtime/test_programmer_incomplete_import_patch.py",
    "tests/runtime/test_programmer_fstring_brace_offset_patch.py",
    "tests/runtime/test_programmer_trailing_backslash_patch.py",
    "tests/runtime/test_programmer_framework_contract_patch.py",
    "tests/runtime/test_generated_stub_admission.py",
    "tests/runtime/test_project_native_failure_intake.py",
    "tests/runtime/test_project_development.py",
    "tests/runtime/test_project_recognition.py",
    "tests/runtime/test_role_project_type_evaluation.py",
    "tests/runtime/test_config_diagnostics.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--matrix", required=True)
    parser.add_argument(
        "--catalog",
        default="knowledge/role_knowledge/project_native_failure_repair_patterns.json",
    )
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    regression = _run_bounded_process(
        [sys.executable, "-m", "pytest", *REGRESSION_FILES, "-q", "--basetemp=.pytest-tmp-native-promotion"],
        cwd=root,
        env=dict(os.environ),
        timeout=180,
    )
    doctor = run_config_doctor(root)
    line_limit = all(
        len((root / path).read_text(encoding="utf-8").splitlines()) <= 400
        for path in (
            "runtime/project_native_repair_promotion.py",
            "runtime/programmer_falsy_empty_patch.py",
            "runtime/programmer_registry_fallback_patch.py",
            "runtime/programmer_timestamp_range_patch.py",
            "runtime/programmer_trailing_backslash_patch.py",
            "runtime/programmer_framework_contract_patch.py",
        )
    )
    report = promote_native_repair_patterns(
        root=root,
        matrix_path=Path(args.matrix),
        explicit_approval=args.approve,
        regression_passed=regression.returncode == 0,
        config_doctor_passed=doctor.get("status") == "ok",
        line_limit_passed=line_limit,
        catalog_path=Path(args.catalog),
    )
    report["regression_summary"] = _tail(regression.stdout)
    report["config_doctor_summary"] = dict(doctor.get("summary") or {})
    if args.write:
        out = root / "artifacts" / "role_promotion"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"project_native_repair_promotion_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "promoted" else 2


def _tail(output: str) -> str:
    return "\n".join(output.strip().splitlines()[-3:])


if __name__ == "__main__":
    raise SystemExit(main())
