"""Hypothesis Compiler extension for the split config doctor."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from runtime._parts.config_doctor_part1 import run_config_doctor as _base_run_config_doctor
from runtime.evaluation_protocol_policy import load_evaluation_protocol_policy
from runtime.three_route_evaluation import manifest_drift_errors
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
    protocol_errors = []
    try:
        load_evaluation_protocol_policy(base / "config" / "evaluation_protocol_v2.json")
    except Exception as exc:  # noqa: BLE001 - doctor reports configuration failures.
        protocol_errors.append(f"{type(exc).__name__}:{exc}")
    report["checks"].append({
        "code": "evaluation_protocol_v2_integrity",
        "status": "failed" if protocol_errors else "passed",
        "errors": protocol_errors,
        "warnings": [],
    })
    report["summary"]["failed"] += int(bool(protocol_errors))
    report["summary"]["passed"] += int(not protocol_errors)
    manifest_errors = []
    try:
        manifest = json.loads((base / "evaluation" / "protocol_v2_manifest.json").read_text(encoding="utf-8"))
        manifest_errors.extend(manifest_drift_errors(base, manifest, allow_missing_external_inputs=True))
    except Exception as exc:  # noqa: BLE001 - doctor reports configuration failures.
        manifest_errors.append(f"{type(exc).__name__}:{exc}")
    report["checks"].append({
        "code": "evaluation_manifest_v2_integrity",
        "status": "failed" if manifest_errors else "passed",
        "errors": manifest_errors,
        "warnings": [],
    })
    report["summary"]["failed"] += int(bool(manifest_errors))
    report["summary"]["passed"] += int(not manifest_errors)
    report["status"] = "failed" if report["summary"]["failed"] else "ok"
    return report
