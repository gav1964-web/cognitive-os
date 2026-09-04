"""Replay risk and blocker policy for active exception-pickle application."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

from .exception_pickle_active_application_core import (
    _object_contracts_for_candidate,
    _recipe,
)
from .exception_pickle_active_application_identity import (
    _candidate_project,
    _candidate_target,
)
from .exception_pickle_source_samples import _sample_constructor_value_for_source_file
from .programmer_exception_pickle_patch import exception_pickle_reconstruction_patch

def _candidate_precheck_risk(
    root: Path,
    active_catalog: dict[str, Any],
    row: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]],
) -> int:
    required = [str(value) for value in row.get("required_constructor_parameters") or []]
    stored = [str(value) for value in row.get("stored_constructor_parameters") or []]
    max_inputs = int(
        dict(dict(active_catalog.get("operator") or {}).get("applicability") or {}).get(
            "maximum_required_constructor_inputs"
        )
        or 0
    )
    candidate = {"project": _candidate_project(row), "target": _candidate_target(row)}
    object_contracts = _object_contracts_for_candidate(candidate, admitted_object_contracts)
    source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    risk = 0
    if not required or len(required) > max_inputs:
        risk += 1000
    if not set(required) <= set(stored):
        risk += 800
    if any(
        _sample_constructor_value_for_source_file(
            name,
            source_file=source_file,
            class_name=str(row.get("class_name") or ""),
            object_contracts=object_contracts,
        )
        is None
        for name in required
    ):
        risk += 500
    return risk


def _candidate_static_patch_risk(root: Path, active_catalog: dict[str, Any], row: dict[str, Any]) -> int:
    project = root / str(row.get("project_root") or "")
    path_text = str(row.get("path") or "")
    source_file = project / path_text
    if not source_file.is_file():
        return 1000
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    required = [str(value) for value in row.get("required_constructor_parameters") or []]
    patch = exception_pickle_reconstruction_patch(
        source,
        class_name=str(row.get("class_name") or ""),
        recipe=_recipe(active_catalog, required, root=root, row=row),
    )
    return 0 if patch is not None else 300


def _candidate_replay_risk(root: Path, row: dict[str, Any]) -> int:
    project = root / str(row.get("project_root") or "")
    relative = Path(str(row.get("path") or ""))
    risk = _source_import_risk(project / relative)
    parents = list(relative.parents)
    for parent in parents:
        if str(parent) == ".":
            continue
        risk += _source_import_risk(project / parent / "__init__.py") * 3
    return risk


def _candidate_effective_replay_risk(root: Path, row: dict[str, Any]) -> int:
    if _prefer_direct_file_replay(root, row):
        return _candidate_target_replay_risk(root, row)
    return _candidate_replay_risk(root, row)


def _candidate_target_replay_risk(root: Path, row: dict[str, Any]) -> int:
    project = root / str(row.get("project_root") or "")
    relative = Path(str(row.get("path") or ""))
    return _source_direct_file_residual_risk(project / relative)


def _prefer_direct_file_replay(root: Path, row: dict[str, Any]) -> bool:
    project = root / str(row.get("project_root") or "")
    relative = Path(str(row.get("path") or ""))
    target_risk = _candidate_target_replay_risk(root, row)
    import_risk = _source_import_risk(project / relative)
    has_package_context = any(str(parent) != "." for parent in relative.parents)
    package_init_risk = 0
    for parent in relative.parents:
        if str(parent) == ".":
            continue
        package_init_risk += _source_import_risk(project / parent / "__init__.py")
    return package_init_risk > target_risk or (
        has_package_context and package_init_risk > 0 and target_risk < import_risk
    ) or (
        target_risk == 0
        and import_risk > 3
        and _target_imports_are_direct_file_stubbable(project / relative, maximum_imports=8)
    )


def _source_import_risk(path: Path) -> int:
    return _source_replay_risk(path, include_imports=True)


def _source_direct_file_residual_risk(path: Path) -> int:
    return _source_replay_risk(path, include_imports=False)


def _target_imports_are_direct_file_stubbable(path: Path, *, maximum_imports: int = 8) -> bool:
    if not path.is_file():
        return False
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    import_count = 0
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _import_name_is_stdlib(alias.name):
                    continue
                import_count += 1
                if not _import_name_is_stubbable(alias.name, path):
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                import_count += 1
                continue
            if node.module and _import_name_is_stdlib(node.module):
                continue
            import_count += 1
            if node.module and not _import_name_is_stubbable(node.module, path):
                return False
    return import_count <= maximum_imports


def _import_name_is_stubbable(name: str, path: Path | None = None) -> bool:
    root = name.split(".", 1)[0]
    low_risk_roots = {
        "attr",
    }
    if root in low_risk_roots:
        return True
    if path is not None:
        package_parts = {part for part in path.parent.parts if part.isidentifier()}
        if root in package_parts:
            return True
    return root.startswith("local_") and root.isidentifier()


def _import_name_is_stdlib(name: str) -> bool:
    root = name.split(".", 1)[0]
    return root == "__future__" or root in getattr(sys, "stdlib_module_names", set())


def _source_replay_risk(path: Path, *, include_imports: bool) -> int:
    if not path.is_file():
        return 0
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 20
    risk = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if include_imports:
                risk += 1
        elif isinstance(node, ast.Raise):
            risk += 5
        elif isinstance(node, ast.Call) and _is_metadata_version_call(node):
            risk += 4
    return risk

def _is_metadata_version_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "version":
        text = ast.unparse(func.value) if hasattr(ast, "unparse") else ""
        return "metadata" in text
    return False

def _classify_blocker(
    status: str, checks: dict[str, bool], replay: dict[str, Any] | None
) -> str | None:
    if status == "applied_active_kb":
        return None
    failed = {name for name, passed in checks.items() if not passed}
    if status == "blocked_copy":
        return "sandbox_copy_failed"
    if "active_catalog_loaded" in failed or "operator_is_validated_active" in failed:
        return "active_catalog_unavailable"
    if "project_exists" in failed or "target_file_exists" in failed:
        return "target_source_unavailable"
    if "required_inputs_are_stored" in failed:
        return "constructor_inputs_not_replayable"
    if "required_input_count_is_bounded" in failed:
        return "constructor_input_count_out_of_policy"
    if "semantic_samples_supported" in failed:
        return "semantic_sample_shape_unsupported"
    if status == "blocked_static_patch":
        return "static_patch_shape_unsupported"
    if "project_native_semantic_replay" in failed:
        return _classify_replay_blocker(replay or {})
    if "patch_compiles" in failed:
        return "patch_compile_failed"
    if "single_file_scope" in failed:
        return "sandbox_scope_expanded"
    if "no_generated_function_stubs" in failed:
        return "generated_stub_detected"
    if "source_digest_unchanged" in failed:
        return "source_digest_changed"
    return "unknown_blocker"


def _classify_replay_blocker(replay: dict[str, Any]) -> str:
    reason = str(replay.get("reason") or "")
    stderr = str(replay.get("stderr") or "")
    if reason == "unsupported_constructor_sample":
        return "semantic_sample_shape_unsupported"
    if "ModuleNotFoundError" in stderr or "DistributionNotFound" in stderr:
        return "semantic_replay_dependency_unavailable"
    if "ImportError" in stderr:
        return "semantic_replay_import_failed"
    if reason in {"TimeoutExpired", "TimeoutError"}:
        return "semantic_replay_timeout"
    if replay.get("status") == "failed":
        return "semantic_replay_behavior_mismatch"
    return "semantic_replay_unavailable"


def _replay_blocker_limit_reached(attempts: list[dict[str, Any]], limit: int | None) -> bool:
    if limit is None or limit <= 0:
        return False
    replay_blockers = [
        str(dict(row).get("blocker_kind") or "")
        for row in attempts
        if str(dict(row).get("blocker_kind") or "").startswith("semantic_replay_")
    ]
    return len(replay_blockers) >= limit


def _blocker_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        kind = dict(row).get("blocker_kind")
        if not kind:
            continue
        summary[str(kind)] = summary.get(str(kind), 0) + 1
    return dict(sorted(summary.items()))
