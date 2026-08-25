"""Hypothesis Compiler extension for the split config doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime._parts.config_doctor_part1 import run_config_doctor as _base_run_config_doctor
from runtime.self_improvement_hypothesis_compiler import load_hypothesis_compiler_config


def run_config_doctor(root: Path | None = None) -> dict[str, Any]:
    report = _base_run_config_doctor(root)
    base = Path(root or Path(__file__).resolve().parents[2]).resolve()
    errors = []
    try:
        load_hypothesis_compiler_config(str(base / "config" / "hypothesis_compiler.json"))
    except Exception as exc:  # noqa: BLE001 - doctor reports configuration failures.
        errors.append(f"{type(exc).__name__}:{exc}")
    report["checks"].append({
        "code": "hypothesis_compiler_integrity",
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": [],
    })
    report["summary"]["failed"] += int(bool(errors))
    report["summary"]["passed"] += int(not errors)
    report["status"] = "failed" if report["summary"]["failed"] else "ok"
    return report
