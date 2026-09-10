"""Frontier selection helpers for active exception-pickle application."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from .exception_pickle_active_application_core import _object_contracts_for_candidate
from .exception_pickle_active_application_identity import (
    _candidate_key,
    _candidate_project,
    _candidate_target,
)
from .exception_pickle_active_application_replay_policy import (
    _candidate_effective_replay_risk,
    _candidate_static_patch_risk,
)
from .exception_pickle_constructor_samples import _sample_constructor_value
from .exception_pickle_source_samples import _sample_constructor_value_for_source_file

def _excluded_projects(transfer_ledger: dict[str, Any], application_ledger: dict[str, Any]) -> set[str]:
    rows = [
        *list(transfer_ledger.get("cases") or []),
        *list(transfer_ledger.get("autonomous_cases") or []),
        *list(application_ledger.get("cases") or []),
    ]
    return {str(dict(row).get("project") or "") for row in rows if isinstance(row, dict)}


def _excluded_target_keys(
    root: Path,
    application_ledger: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
    rows_by_key: dict[str, dict[str, Any]],
    readmission_eligible_targets: set[str] | None = None,
    import_isolation_frontier_targets: set[str] | None = None,
) -> set[str]:
    applied = {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in application_ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }
    rows = _latest_blocked_rows_by_target(application_ledger)
    readmission_eligible_targets = readmission_eligible_targets or set()
    import_isolation_frontier_targets = import_isolation_frontier_targets or set()
    return applied | {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in rows.values()
        if (
            isinstance(row, dict)
            and f"{dict(row).get('project')}::{dict(row).get('target')}"
            not in import_isolation_frontier_targets
            and not (
                row.get("blocker_kind") == "semantic_sample_shape_unsupported"
                and (
                    f"{dict(row).get('project')}::{dict(row).get('target')}" in admitted_object_contracts
                    or f"{dict(row).get('project')}::{dict(row).get('target')}" in readmission_eligible_targets
                )
            )
            and not (
                row.get("blocker_kind") == "static_patch_shape_unsupported"
                and f"{dict(row).get('project')}::{dict(row).get('target')}" in readmission_eligible_targets
            )
        )
    }


def _readmission_frontier_target_keys(
    root: Path,
    application_ledger: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
    rows_by_key: dict[str, dict[str, Any]],
    readmission_eligible_targets: set[str],
) -> set[str]:
    latest = _latest_blocked_rows_by_target(application_ledger)
    applied = {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in application_ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }
    return {
        key
        for key, row in latest.items()
        if key not in applied
        if (
            row.get("blocker_kind") == "semantic_sample_shape_unsupported"
            and (key in admitted_object_contracts or key in readmission_eligible_targets)
        )
        or (
            row.get("blocker_kind") == "static_patch_shape_unsupported"
            and key in readmission_eligible_targets
        )
    }


def _import_isolation_frontier_target_keys(
    root: Path,
    application_ledger: dict[str, Any],
    active_catalog: dict[str, Any],
    rows_by_key: dict[str, dict[str, Any]],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> set[str]:
    latest = _latest_blocked_rows_by_target(application_ledger)
    applied = {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in application_ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }
    targets: set[str] = set()
    for key, blocked in latest.items():
        if key in applied:
            continue
        row = rows_by_key.get(key)
        if not row:
            continue
        if _candidate_static_patch_risk(root, active_catalog, row) != 0:
            continue
        blocker_kind = str(blocked.get("blocker_kind") or "")
        if blocker_kind in {"semantic_replay_dependency_unavailable", "semantic_replay_import_failed"}:
            targets.add(key)
            continue
        if blocker_kind == "semantic_replay_behavior_mismatch" and _source_has_attribute_base_class_definition(
            root / str(row.get("project_root") or "") / str(row.get("path") or "")
        ):
            targets.add(key)
            continue
        if (
            blocker_kind == "semantic_sample_shape_unsupported"
            and _candidate_samples_supported(root, row, admitted_object_contracts)
            and _candidate_effective_replay_risk(root, row) > 3
        ):
            targets.add(key)
    return targets


def _import_isolation_targets_by_missing_kind(root: Path, missing_kind: str) -> set[str]:
    report = _latest_blocker_intelligence_report(root)
    targets: set[str] = set()
    for case in report.get("cases") or []:
        if not isinstance(case, dict):
            continue
        if case.get("next_operator_lane") != "import_dependency_isolation_candidate":
            continue
        profile = case.get("import_isolation_profile")
        if not isinstance(profile, dict):
            continue
        if str(profile.get("missing_import_kind") or "") != missing_kind:
            continue
        targets.add(f"{case.get('project')}::{case.get('target')}")
    return targets


def _import_isolation_targets_by_batch_profile(
    root: Path,
    profile_name: str,
    *,
    import_isolation_cluster: str | None = None,
) -> dict[str, Any]:
    report = _latest_blocker_intelligence_report(root)
    if profile_name not in {"dependency_heavy_direct_file", "project_local_direct_file"}:
        return {
            "profile": profile_name,
            "status": "unsupported_profile",
            "targets": [],
            "case_count": 0,
        }
    expected_missing_kind = (
        "project_local_dependency"
        if profile_name == "project_local_direct_file"
        else "external_dependency"
    )
    targets: list[str] = []
    missing_imports: dict[str, int] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, dict):
            continue
        if case.get("next_operator_lane") != "import_dependency_isolation_candidate":
            continue
        profile = case.get("import_isolation_profile")
        if not isinstance(profile, dict):
            continue
        missing_kind = str(profile.get("missing_import_kind") or "")
        subtype = str(profile.get("subtype") or "")
        if missing_kind != expected_missing_kind:
            continue
        if profile.get("direct_file_preferred") is not True:
            continue
        if int(profile.get("target_replay_risk") or 0) > 3:
            continue
        if subtype not in {"dependency_unavailable", "import_failed"}:
            continue
        if expected_missing_kind == "project_local_dependency" and (
            profile.get("has_attribute_base_class_definition") is True
            or profile.get("has_target_self_attribute_gap") is True
        ):
            continue
        if expected_missing_kind == "external_dependency":
            cluster = f"external_dependency:{str(profile.get('missing_import') or '').split('.', 1)[0]}"
        else:
            cluster = f"project_local_dependency:{subtype or 'unknown'}"
        if import_isolation_cluster and cluster != import_isolation_cluster:
            continue
        key = f"{case.get('project')}::{case.get('target')}"
        targets.append(key)
        missing = str(profile.get("missing_import") or "")
        if missing:
            missing_imports[missing] = missing_imports.get(missing, 0) + 1
    return {
        "profile": profile_name,
        "cluster": import_isolation_cluster,
        "status": "ready",
        "case_count": len(targets),
        "targets": targets,
        "missing_import_summary": dict(sorted(missing_imports.items())),
        "selection_constraints": {
            "missing_import_kind": expected_missing_kind,
            "direct_file_preferred": True,
            "maximum_target_replay_risk": 3,
            "allowed_subtypes": ["dependency_unavailable", "import_failed"],
            "attribute_base_class_definitions": "excluded",
            "target_self_attribute_gaps": "excluded",
        },
    }


def _latest_blocker_intelligence_report(root: Path) -> dict[str, Any]:
    report_dir = root / "artifacts" / "project_development"
    if not report_dir.is_dir():
        return {}
    paths = sorted(report_dir.glob("exception_pickle_blocker_intelligence_*.json"))
    for path in reversed(paths):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(report, dict) and report.get("artifact_type") == "ExceptionPickleBlockerIntelligence":
            return report
    return {}


def _latest_blocked_rows_by_target(application_ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in application_ledger.get("blocked_cases") or []:
        if not isinstance(row, dict):
            continue
        key = f"{row.get('project')}::{row.get('target')}"
        latest[key] = dict(row)
    return latest


def _candidate_samples_supported(
    root: Path,
    row: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> bool:
    candidate = {"project": _candidate_project(row), "target": _candidate_target(row)}
    object_contracts = _object_contracts_for_candidate(candidate, admitted_object_contracts)
    required = [str(value) for value in row.get("required_constructor_parameters") or []]
    source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    return bool(required) and all(
        _sample_constructor_value_for_source_file(
            name,
            source_file=source_file,
            class_name=str(row.get("class_name") or ""),
            object_contracts=object_contracts,
        )
        is not None
        for name in required
    )


def _readmission_eligible_target_keys(
    root: Path,
    active_catalog: dict[str, Any],
    rows_by_key: dict[str, dict[str, Any]],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> set[str]:
    eligible: set[str] = set()
    for key, row in rows_by_key.items():
        candidate = {"project": _candidate_project(row), "target": _candidate_target(row)}
        object_contracts = _object_contracts_for_candidate(candidate, admitted_object_contracts)
        required = [str(value) for value in row.get("required_constructor_parameters") or []]
        source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
        if required and all(
            _sample_constructor_value_for_source_file(
                name,
                source_file=source_file,
                class_name=str(row.get("class_name") or ""),
                object_contracts=object_contracts,
            )
            is not None
            for name in required
        ):
            if _candidate_static_patch_risk(root, active_catalog, row) != 0:
                continue
            if _candidate_effective_replay_risk(root, row) > 3:
                continue
            eligible.add(key)
    return eligible


def _candidate_has_source_aware_sample_override(
    root: Path,
    row: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> bool:
    if not row:
        return False
    candidate = {"project": _candidate_project(row), "target": _candidate_target(row)}
    object_contracts = _object_contracts_for_candidate(candidate, admitted_object_contracts)
    source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    for name in [str(value) for value in row.get("required_constructor_parameters") or []]:
        base = _sample_constructor_value(name, object_contracts=object_contracts)
        source_aware = _sample_constructor_value_for_source_file(
            name,
            source_file=source_file,
            class_name=str(row.get("class_name") or ""),
            object_contracts=object_contracts,
        )
        if source_aware is not None and source_aware != base:
            return True
    return False


def _candidate_has_materializer_behavior_readmission_delta(
    root: Path,
    row: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> bool:
    return _candidate_has_source_aware_sample_override(
        root,
        row,
        admitted_object_contracts,
    ) or any(
        str(value).lower() in {"flag", "param", "transformer"}
        for value in row.get("required_constructor_parameters") or []
    )


def _candidate_has_self_reference_args_readmission_delta(root: Path, row: dict[str, Any]) -> bool:
    if not row:
        return False
    source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    return _class_has_self_reference_super_init(source_file, str(row.get("class_name") or ""))

def _class_has_self_reference_super_init(source_file: Path, class_name: str) -> bool:
    if not source_file.is_file() or not class_name.isidentifier():
        return False
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    if any(isinstance(base, ast.Attribute) for node in classes for base in node.bases):
        return False
    for node in classes:
        if node.name != class_name:
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            func = inner.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "__init__"
                and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name)
                and func.value.func.id == "super"
            ):
                continue
            if inner.args and isinstance(inner.args[0], ast.Name) and inner.args[0].id == "self":
                return True
    return False


def _source_has_attribute_base_class_definition(source_file: Path) -> bool:
    if not source_file.is_file():
        return False
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Attribute) for base in node.bases)
        for node in ast.walk(tree)
    )
