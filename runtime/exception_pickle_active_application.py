"""Apply an active exception-pickle KB pattern to holdout candidates in sandbox."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_active_application_core import _attempt_result, _object_contracts_for_candidate, _read_json, _read_optional_json, _recipe, _write_application_ledger
from .exception_pickle_active_application_identity import _candidate_key, _candidate_project, _candidate_readmission_subtype, _candidate_target
from .exception_pickle_active_application_replay_policy import (
    _candidate_effective_replay_risk,
    _candidate_precheck_risk,
    _candidate_replay_risk,
    _candidate_static_patch_risk,
    _blocker_summary,
    _classify_blocker,
    _prefer_direct_file_replay,
    _replay_blocker_limit_reached,
)
from .exception_pickle_active_application_selection import (
    _excluded_projects,
    _excluded_target_keys,
    _candidate_has_materializer_behavior_readmission_delta,
    _candidate_has_self_reference_args_readmission_delta,
    _candidate_has_source_aware_sample_override,
    _import_isolation_frontier_target_keys,
    _import_isolation_targets_by_batch_profile,
    _import_isolation_targets_by_missing_kind,
    _readmission_eligible_target_keys,
    _readmission_frontier_target_keys,
)
from .exception_pickle_autonomous_shadow import _changed_python_files, _compiles, _sample_constructor_value_for_source_file, _verify_project_native_semantic_replay
from .exception_pickle_holdout_transaction import DEFAULT_AUDIT, DEFAULT_LEDGER
from .exception_pickle_object_contract_admission import load_admitted_object_contracts
from .generated_stub_admission import inspect_generated_function_stubs
from .programmer_exception_pickle_patch import exception_pickle_reconstruction_patch
from .project_development_boundary_interpreter import load_exception_pickle_patterns


DEFAULT_APPLICATION_LEDGER = Path(
    "artifacts/project_development/exception_pickle_active_application_ledger.json"
)


def run_exception_pickle_active_application_trial(
    *,
    root: Path,
    execution_dir: Path,
    audit_path: Path = DEFAULT_AUDIT,
    transfer_ledger_path: Path = DEFAULT_LEDGER,
    application_ledger_path: Path = DEFAULT_APPLICATION_LEDGER,
    object_contract_admission_path: Path | None = None,
    maximum_attempts: int = 8,
    maximum_accepted_applications: int = 1,
    maximum_replay_blockers: int | None = None,
    maximum_static_patch_blockers_per_project: int = 1,
    maximum_replay_blockers_per_project: int = 1,
    prioritize_patchable_candidates: bool = True,
    prioritize_dependency_light_candidates: bool = True,
    allow_target_import_stubs: bool = True,
    only_readmission_frontier: bool = False,
    only_import_isolation_frontier: bool = False,
    readmission_subtype: str | None = None,
    import_isolation_missing_kind: str | None = None,
    import_isolation_batch_profile: str | None = None,
    import_isolation_cluster: str | None = None,
    candidate_keys: list[str] | None = None,
    update_application_ledger: bool = True,
) -> dict[str, Any]:
    """Try active KB application on holdout candidates without source mutation."""
    root = root.resolve()
    active_catalog = load_exception_pickle_patterns(
        str(root / "knowledge" / "role_knowledge" / "exception_pickle_reconstruction_patterns.json")
    )
    audit = _read_json(root, audit_path)
    transfer_ledger = _read_json(root, transfer_ledger_path)
    application_ledger = _read_optional_json(root, application_ledger_path)
    admitted_object_contracts = load_admitted_object_contracts(root, object_contract_admission_path)
    excluded_projects = _excluded_projects(transfer_ledger, application_ledger)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in audit.get("candidates") or []
        if isinstance(row, dict)
    }
    readmission_eligible_targets = _readmission_eligible_target_keys(
        root,
        active_catalog,
        rows_by_key,
        admitted_object_contracts,
    )
    readmission_frontier_targets = _readmission_frontier_target_keys(
        root,
        application_ledger,
        admitted_object_contracts,
        rows_by_key,
        readmission_eligible_targets,
    )
    import_isolation_frontier_targets = _import_isolation_frontier_target_keys(
        root,
        application_ledger,
        active_catalog,
        rows_by_key,
        admitted_object_contracts,
    )
    if import_isolation_missing_kind:
        import_isolation_frontier_targets &= _import_isolation_targets_by_missing_kind(
            root,
            import_isolation_missing_kind,
        )
    import_isolation_batch_summary: dict[str, Any] = {}
    if import_isolation_batch_profile:
        batch = _import_isolation_targets_by_batch_profile(
            root,
            import_isolation_batch_profile,
            import_isolation_cluster=import_isolation_cluster,
        )
        import_isolation_frontier_targets &= set(batch.get("targets") or [])
        import_isolation_batch_summary = {
            key: value for key, value in batch.items() if key != "targets"
        }
    explicit_candidate_keys = {str(key) for key in candidate_keys or [] if str(key)}
    excluded_targets = _excluded_target_keys(
        root,
        application_ledger,
        admitted_object_contracts,
        rows_by_key,
        readmission_eligible_targets,
        import_isolation_frontier_targets if only_import_isolation_frontier else set(),
    )
    candidates = [
        dict(row)
        for row in audit.get("candidates") or []
        if (
            isinstance(row, dict)
            and (
                only_readmission_frontier
                or only_import_isolation_frontier
                or explicit_candidate_keys
                or _candidate_project(row) not in excluded_projects
            )
            and (not explicit_candidate_keys or _candidate_key(row) in explicit_candidate_keys)
            and (
                _candidate_key(row) not in excluded_targets
                or _candidate_key(row) in explicit_candidate_keys
            )
            and (not only_readmission_frontier or _candidate_key(row) in readmission_frontier_targets)
            and (
                not only_import_isolation_frontier
                or _candidate_key(row) in import_isolation_frontier_targets
            )
            and (
                not readmission_subtype
                or _candidate_readmission_subtype(row) == readmission_subtype
            )
        )
    ]
    candidates.sort(
        key=lambda row: (
            _candidate_precheck_risk(root, active_catalog, row, admitted_object_contracts),
            _candidate_static_patch_risk(root, active_catalog, row)
            if prioritize_patchable_candidates
            else 0,
            _candidate_effective_replay_risk(root, row) if prioritize_dependency_light_candidates else 0,
            -int(row.get("score") or 0),
            _candidate_project(row),
            str(row.get("path") or ""),
        )
    )
    attempts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    static_patch_blockers_by_project: dict[str, int] = {}
    replay_blockers_by_project: dict[str, int] = {}
    selected_applications: list[dict[str, Any]] = []
    stop_reason = "candidate_frontier_exhausted"
    for row in candidates:
        if len(attempts) >= maximum_attempts:
            stop_reason = "maximum_attempts_reached"
            break
        if maximum_accepted_applications > 0 and len(selected_applications) >= maximum_accepted_applications:
            stop_reason = "maximum_accepted_applications_reached"
            break
        project_name = _candidate_project(row)
        if (
            maximum_static_patch_blockers_per_project > 0
            and static_patch_blockers_by_project.get(project_name, 0)
            >= maximum_static_patch_blockers_per_project
        ):
            skipped.append({
                "project": project_name,
                "target": _candidate_target(row),
                "reason": "project_static_patch_blocker_budget_reached",
            })
            continue
        if (
            maximum_replay_blockers_per_project > 0
            and replay_blockers_by_project.get(project_name, 0)
            >= maximum_replay_blockers_per_project
        ):
            skipped.append({
                "project": project_name,
                "target": _candidate_target(row),
                "reason": "project_replay_blocker_budget_reached",
            })
            continue
        result = _attempt_candidate(
            root=root,
            execution_dir=execution_dir / f"attempt-{len(attempts) + 1}",
            source_row=row,
            active_catalog=active_catalog,
            admitted_object_contracts=admitted_object_contracts,
            allow_target_import_stubs=allow_target_import_stubs,
        )
        attempts.append(result)
        if result.get("blocker_kind") == "static_patch_shape_unsupported":
            static_patch_blockers_by_project[project_name] = (
                static_patch_blockers_by_project.get(project_name, 0) + 1
            )
        if str(result.get("blocker_kind") or "").startswith("semantic_replay_"):
            replay_blockers_by_project[project_name] = (
                replay_blockers_by_project.get(project_name, 0) + 1
            )
        if result.get("status") == "applied_active_kb":
            selected_applications.append(result)
            if (
                maximum_accepted_applications > 0
                and len(selected_applications) >= maximum_accepted_applications
            ):
                stop_reason = "maximum_accepted_applications_reached"
                break
            continue
        if _replay_blocker_limit_reached(attempts, maximum_replay_blockers):
            stop_reason = "maximum_replay_blockers_reached"
            break
    selected_result = selected_applications[0] if selected_applications else None
    report = {
        "artifact_type": "ExceptionPickleActiveApplicationTrial",
        "schema_version": "exception_pickle_active_application_trial.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "applied_active_kb" if selected_result else "blocked",
        "selected_application": selected_result,
        "selected_applications": selected_applications,
        "selected_application_count": len(selected_applications),
        "stop_reason": stop_reason,
        "attempts": attempts,
        "skipped_candidates": skipped,
        "skipped_candidate_count": len(skipped),
        "attempt_count": len(attempts),
        "maximum_accepted_applications": maximum_accepted_applications,
        "maximum_replay_blockers": maximum_replay_blockers,
        "maximum_static_patch_blockers_per_project": maximum_static_patch_blockers_per_project,
        "maximum_replay_blockers_per_project": maximum_replay_blockers_per_project,
        "prioritize_patchable_candidates": prioritize_patchable_candidates,
        "prioritize_dependency_light_candidates": prioritize_dependency_light_candidates,
        "allow_target_import_stubs": allow_target_import_stubs,
        "only_readmission_frontier": only_readmission_frontier,
        "only_import_isolation_frontier": only_import_isolation_frontier,
        "readmission_subtype": readmission_subtype,
        "import_isolation_missing_kind": import_isolation_missing_kind,
        "import_isolation_batch_profile": import_isolation_batch_profile,
        "import_isolation_cluster": import_isolation_cluster,
        "candidate_keys": sorted(explicit_candidate_keys),
        "import_isolation_batch_summary": import_isolation_batch_summary,
        "update_application_ledger": update_application_ledger,
        "replay_blocker_limit_reached": _replay_blocker_limit_reached(attempts, maximum_replay_blockers),
        "blocker_summary": _blocker_summary(attempts),
        "selection_policy": "strict_readmission_precheck_patchability_dependency_light_and_project_static_budget",
        "source_apply": False,
        "kb_promotion": False,
    }
    if update_application_ledger:
        _write_application_ledger(root, application_ledger_path, transfer_ledger, application_ledger, report)
    return report


def _attempt_candidate(
    *,
    root: Path,
    execution_dir: Path,
    source_row: dict[str, Any],
    active_catalog: dict[str, Any],
    admitted_object_contracts: dict[str, dict[str, Any]] | None = None,
    allow_target_import_stubs: bool = True,
) -> dict[str, Any]:
    project = root / str(source_row.get("project_root") or "")
    path_text = str(source_row.get("path") or "")
    source_file = project / path_text
    candidate = {
        "project": _candidate_project(source_row),
        "target": f"{path_text}:{source_row.get('class_name')}.__init__",
        "score": source_row.get("score"),
    }
    required = [str(value) for value in source_row.get("required_constructor_parameters") or []]
    stored = [str(value) for value in source_row.get("stored_constructor_parameters") or []]
    object_contracts = _object_contracts_for_candidate(candidate, admitted_object_contracts or {})
    samples_supported = all(
        _sample_constructor_value_for_source_file(
            name,
            source_file=source_file,
            class_name=str(source_row.get("class_name") or ""),
            object_contracts=object_contracts,
        )
        is not None
        for name in required
    )
    recipe = _recipe(active_catalog, required, root=root, row=source_row)
    prechecks = {
        "active_catalog_loaded": active_catalog.get("status") == "active",
        "operator_is_validated_active": dict(active_catalog.get("operator") or {}).get("status")
        == "validated_active",
        "project_exists": project.is_dir(),
        "target_file_exists": source_file.is_file(),
        "required_inputs_are_stored": set(required) <= set(stored),
        "required_input_count_is_bounded": 0 < len(required) <= int(
            dict(dict(active_catalog.get("operator") or {}).get("applicability") or {}).get(
                "maximum_required_constructor_inputs"
            )
            or 0
        ),
        "semantic_samples_supported": samples_supported,
    }
    if not all(prechecks.values()):
        return _attempt_result("blocked_precheck", candidate, prechecks)
    before = hashlib.sha256(source_file.read_bytes()).hexdigest()
    sandbox = execution_dir / "sandbox_project"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    try:
        shutil.copytree(
            project,
            sandbox,
            ignore=shutil.ignore_patterns(
                ".git",
                ".pytest_cache",
                "__pycache__",
                "*.pyc",
                ".venv",
                "venv",
                "build_cache",
            ),
        )
    except (OSError, shutil.Error):
        return _attempt_result("blocked_copy", candidate, prechecks, sandbox=sandbox)
    sandbox_file = sandbox / path_text
    original = sandbox_file.read_text(encoding="utf-8")
    patch = exception_pickle_reconstruction_patch(
        original,
        class_name=str(source_row.get("class_name") or ""),
        recipe=recipe,
    )
    if patch is None:
        return _attempt_result("blocked_static_patch", candidate, prechecks, sandbox=sandbox)
    sandbox_file.write_text(str(patch["source"]), encoding="utf-8")
    stub = inspect_generated_function_stubs(
        original_project=project,
        sandbox_project=sandbox,
        patch={"patches": [{"file": path_text, "target": candidate["target"]}]},
    )
    changed = _changed_python_files(project, sandbox)
    checks = {
        **prechecks,
        "patch_compiles": _compiles(str(patch["source"]), path_text),
        "single_file_scope": changed == [path_text.replace("\\", "/")],
        "no_generated_function_stubs": stub.get("status") == "passed",
        "source_digest_unchanged": hashlib.sha256(source_file.read_bytes()).hexdigest() == before,
    }
    replay = (
        _verify_project_native_semantic_replay(
            sandbox=sandbox,
            source_row=source_row,
            state_attributes=list(patch["stored_inputs"]),
            object_contracts=object_contracts,
            allow_target_import_stubs=allow_target_import_stubs,
            prefer_direct_file_import=_prefer_direct_file_replay(root, source_row),
        )
        if all(checks.values())
        else {"status": "not_requested", "reason": "static_checks_failed"}
    )
    checks["project_native_semantic_replay"] = replay.get("status") == "passed"
    status = "applied_active_kb" if all(checks.values()) else "blocked_semantic_replay"
    return {
        "artifact_type": "ExceptionPickleActiveApplicationAttempt",
        "status": status,
        "candidate": candidate,
        "operator_id": recipe["operator_id"],
        "required_constructor_inputs": required,
        "object_contracts": object_contracts,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "blocker_kind": _classify_blocker(status, checks, replay),
        "project_native_semantic_replay": replay,
        "sandbox_project": sandbox.as_posix(),
        "sandbox_changed_python_files": changed,
        "source_apply": False,
        "kb_promotion": False,
    }


