"""Aggregate case-level stub admissions and bind them to source report digests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def build_generated_function_stub_audit(report_paths: list[Path]) -> dict[str, Any]:
    reports: dict[str, str] = {}
    violations: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []
    missing_admissions: list[dict[str, Any]] = []
    case_count = 0
    for raw_path in report_paths:
        path = raw_path.resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        reports[path.as_posix()] = _bytes_digest(path.read_bytes())
        for index, case in enumerate(payload.get("cases") or []):
            if not isinstance(case, dict):
                continue
            case_count += 1
            admission = dict(case.get("generated_function_stub_admission") or {})
            context = {"report": path.as_posix(), "case": index, "project": case.get("project")}
            if admission.get("artifact_type") != "GeneratedFunctionStubAdmission":
                missing_admissions.append(context)
                continue
            violations.extend({**context, **row} for row in admission.get("violations") or [])
            parse_failures.extend({**context, **row} for row in admission.get("parse_failures") or [])
    checks = {
        "reports_present": bool(reports),
        "cases_present": case_count > 0,
        "all_cases_have_admission": not missing_admissions,
        "all_generated_files_parse": not parse_failures,
        "zero_generated_function_stubs": not violations,
    }
    body = {
        "artifact_type": "GeneratedFunctionStubAudit",
        "schema_version": "generated_function_stub_audit.v1",
        "status": "passed" if all(checks.values()) else "blocked",
        "report_digests": dict(sorted(reports.items())),
        "case_count": case_count,
        "generated_stub_count": len(violations),
        "violations": violations,
        "parse_failures": parse_failures,
        "missing_admissions": missing_admissions,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    return {**body, "audit_digest": _digest(body)}


def _bytes_digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _bytes_digest(encoded)
