"""Fail-closed promotion transaction for project-native repair knowledge."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CATALOG_PATH = Path("knowledge/role_knowledge/project_native_failure_repair_patterns.json")
REQUIRED_ROLES = {
    "project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer",
}


def promote_native_repair_patterns(
    *,
    root: Path,
    matrix_path: Path,
    explicit_approval: bool,
    regression_passed: bool,
    config_doctor_passed: bool,
    line_limit_passed: bool,
    catalog_path: Path = CATALOG_PATH,
) -> dict[str, Any]:
    root = root.resolve()
    relative_catalog = catalog_path
    catalog_path = catalog_path if catalog_path.is_absolute() else root / catalog_path
    before = catalog_path.read_bytes()
    catalog = json.loads(before.decode("utf-8"))
    matrix = _read_json(root, matrix_path)
    checks, evidence = _promotion_checks(
        root=root,
        catalog=catalog,
        matrix=matrix,
        explicit_approval=explicit_approval,
        regression_passed=regression_passed,
        config_doctor_passed=config_doctor_passed,
        line_limit_passed=line_limit_passed,
    )
    report = {
        "artifact_type": "ProjectNativeRepairPromotionTransaction",
        "schema_version": "project_native_repair_promotion.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "promoted" if all(checks.values()) else "blocked",
        "catalog_path": _relative(root, relative_catalog),
        "matrix_path": _relative(root, matrix_path),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "evidence": evidence,
        "before_digest": hashlib.sha256(before).hexdigest(),
        "source_project_changes": 0,
    }
    if report["status"] != "promoted":
        report["after_digest"] = report["before_digest"]
        return report

    promoted_at = report["generated_at"]
    catalog["status"] = "active"
    catalog["promotion_policy"]["status"] = "active"
    catalog["promotion_policy"]["promoted_at"] = promoted_at
    catalog["promotion_policy"]["promotion_authority"] = "explicit_verified_transaction"
    catalog["promotion_policy"]["promotion_matrix"] = report["matrix_path"]
    for pattern in catalog.get("patterns") or []:
        pattern["status"] = "validated_active"
        pattern["promotion_ready"] = True
        pattern["promotion_blockers"] = []
    encoded = (json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(catalog_path, encoded)
    try:
        reloaded = json.loads(catalog_path.read_text(encoding="utf-8"))
        if reloaded.get("promotion_policy", {}).get("status") != "active":
            raise ValueError("promoted catalog did not reload as active")
    except Exception:
        _atomic_write(catalog_path, before)
        raise
    report["after_digest"] = hashlib.sha256(encoded).hexdigest()
    return report


def _promotion_checks(
    *, root: Path, catalog: dict[str, Any], matrix: dict[str, Any], explicit_approval: bool,
    regression_passed: bool, config_doctor_passed: bool, line_limit_passed: bool,
) -> tuple[dict[str, bool], dict[str, Any]]:
    policy = dict(catalog.get("promotion_policy") or {})
    patterns = [dict(row) for row in catalog.get("patterns") or [] if isinstance(row, dict)]
    projects = {str(dict(row.get("validated_evidence") or {}).get("project") or "") for row in patterns}
    subtypes = {str(row.get("failure_kind") or "") for row in patterns}
    development = [_development_evidence(root, row) for row in patterns]
    project_stratum = str(policy.get("project_stratum") or "library_pure_transform")
    matrix_rows = [
        dict(row) for row in matrix.get("cells") or []
        if row.get("project_stratum") == project_stratum
        and row.get("role_id") in REQUIRED_ROLES
    ]
    minimum_transformations = int(policy.get("minimum_project_native_transformations") or 0)
    checks = {
        "explicit_approval": explicit_approval,
        "catalog_threshold_waiting": policy.get("status") in {
            "threshold_met_awaiting_explicit_promotion", "active",
        },
        "minimum_transformations": len(patterns) >= minimum_transformations,
        "minimum_independent_lineages": len(projects - {""}) >= int(policy.get("minimum_independent_lineages") or 0),
        "minimum_transformation_subtypes": len(subtypes - {""}) >= int(policy.get("minimum_transformation_subtypes") or 0),
        "all_native_outcomes_verified": bool(development) and all(row["verified"] for row in development),
        "matrix_roles_complete": {str(row.get("role_id")) for row in matrix_rows} == REQUIRED_ROLES,
        "matrix_native_threshold_met": bool(matrix_rows) and all(
            int(row.get("project_native_transformation_count") or 0) >= minimum_transformations
            and row.get("maturity") == "mature"
            and not row.get("evidence_gaps")
            for row in matrix_rows
        ),
        "regression_tests": regression_passed,
        "config_doctor": config_doctor_passed,
        "line_limit_check": line_limit_passed,
    }
    return checks, {
        "projects": sorted(projects - {""}),
        "failure_kinds": sorted(subtypes - {""}),
        "project_stratum": project_stratum,
        "development_reports": development,
        "matrix_roles": sorted(str(row.get("role_id")) for row in matrix_rows),
    }


def _development_evidence(root: Path, pattern: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(pattern.get("validated_evidence") or {})
    relative = str(evidence.get("project_development_report") or "")
    report = _read_json(root, Path(relative)) if relative else {}
    experiment = dict(report.get("experiment") or {})
    native = dict(experiment.get("project_native_verification") or {})
    verified = all((
        report.get("status") == "experiment_validated",
        experiment.get("status") == "verified",
        dict(experiment.get("source_invariant") or {}).get("unchanged") is True,
        native.get("status") == "passed",
        dict(native.get("targeted_replay") or {}).get("status") == "passed",
        dict(native.get("regression_suite") or {}).get("status") == "passed",
        dict(report.get("validated_memory") or {}).get("status") == "validated",
    ))
    return {"project": evidence.get("project"), "path": relative, "verified": verified}


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    return json.loads(resolved.read_text(encoding="utf-8"))


def _relative(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve().relative_to(root).as_posix()


def _atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
