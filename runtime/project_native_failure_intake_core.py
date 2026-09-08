"""Top-level orchestration for project-native failure intake."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_development import load_project_development_policy
from .project_native_failure_binding import _case_status, _failure_kind, _normalize_nodeid
from .project_native_failure_environment import (
    _configure_short_basetemp,
    _copy_git_build_metadata,
    _copy_project,
    _project_digest,
    _project_specific_intake,
    _project_version_hint,
    _slug,
)
from .project_native_failure_pytest import _run_pytest

def run_project_native_failure_intake(
    *,
    root: Path,
    projects: list[Path],
    project_stratum: str,
    test_targets: list[str] | None = None,
    write: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_project_development_policy()
    intake = dict(policy.get("native_failure_intake") or {})
    overlay = Path(str(intake.get("dependency_overlay") or ""))
    intake["dependency_overlay_path"] = (
        (root / overlay).resolve().as_posix() if str(overlay) else ""
    )
    intake["project_dependency_overlay_paths"] = {
        str(name).lower(): (root / Path(str(path))).resolve().as_posix()
        for name, path in dict(intake.get("project_dependency_overlays") or {}).items()
    }
    _configure_short_basetemp(root, intake)
    cache = Path(str(intake.get("shard_cache_directory") or "artifacts/project_native_failure_intake/shard_cache"))
    intake["shard_cache_path"] = str((cache if cache.is_absolute() else root / cache).resolve())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work_root = _intake_work_root(root, stamp, intake)
    selected_test_targets = _validated_test_targets(projects, test_targets or [])
    cases = [
        _run_project_case(
            project=project.resolve(),
            project_stratum=project_stratum,
            work_root=work_root,
            intake=intake,
            test_targets=selected_test_targets,
        )
        for project in projects
    ]
    qualified = [row for row in cases if row["status"] == "qualified_failure"]
    report = {
        "artifact_type": "ProjectNativeFailureIntakeReport",
        "schema_version": "project_native_failure_intake.v1",
        "status": "tasks_ready" if qualified else "no_qualified_failure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_stratum": project_stratum,
        "project_count": len(cases),
        "summary": {
            "qualified_failure_count": len(qualified),
            "clean_baseline_count": sum(row["status"] == "clean_baseline" for row in cases),
            "environment_blocked_count": sum(row["status"] == "environment_blocked" for row in cases),
            "unbound_failure_count": sum(row["status"] == "reproducible_unbound_failure" for row in cases),
            "unstable_failure_count": sum(row["status"] == "unstable_failure" for row in cases),
            "source_project_changes": sum(not row["source_invariant"]["unchanged"] for row in cases),
        },
        "qualified_tasks": [row["change_request"] for row in qualified],
        "cases": cases,
        "policy": {
            "repeat_count": int(intake.get("repeat_count") or 2),
            "runner": "python -m pytest",
            "source_apply": False,
            "test_targets": selected_test_targets,
            "failure_syntax_alone_is_authority": False,
            "shard_on_timeout": bool(intake.get("shard_on_timeout", True)),
            "maximum_shards": int(intake.get("maximum_shards") or 6),
            "shard_timeout_seconds": int(intake.get("shard_timeout_seconds") or 60),
            "timeout_seconds": int(intake.get("timeout_seconds") or 120),
            "maximum_refined_shards": int(intake.get("maximum_refined_shards") or 16),
            "refined_shard_timeout_seconds": int(intake.get("refined_shard_timeout_seconds") or 60),
            "shard_cache_enabled": bool(intake.get("shard_cache_enabled", True)),
            "preserve_bounded_git_build_metadata": bool(
                intake.get("preserve_bounded_git_build_metadata", True)
            ),
            "terminate_process_tree_on_timeout": True,
            "opaque_observers_block_repair_authority": True,
        },
    }
    if write:
        out = root / "artifacts" / "field_trials"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"project_native_failure_intake_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report

def _run_project_case(
    *,
    project: Path,
    project_stratum: str,
    work_root: Path,
    intake: dict[str, Any],
    test_targets: list[str],
) -> dict[str, Any]:
    before = _project_digest(project)
    case_intake = _project_specific_intake(project, intake)
    case_intake["project_version_hint"] = _project_version_hint(project)
    repetitions = []
    repeat_count = max(2, int(intake.get("repeat_count") or 2))
    for index in range(1, repeat_count + 1):
        sandbox = work_root / _slug(project.name) / f"r{index}" / "p"
        _copy_project(project, sandbox, case_intake)
        case_intake["git_build_metadata_preserved"] = _copy_git_build_metadata(
            project, sandbox, case_intake
        )
        repetitions.append(_run_pytest(sandbox, case_intake, nodeids=test_targets or None))
    after = _project_digest(project)
    unchanged = before == after
    status, target = _case_status(repetitions, require_unique=bool(intake.get("require_unique_production_target", True)))
    failure = repetitions[0] if repetitions else {}
    change_request = None
    if status == "qualified_failure" and target and unchanged:
        failure_kind = _failure_kind(
            target,
            str(failure.get("leaf_failure_summary") or failure.get("failure_summary") or ""),
            list(failure.get("failing_nodeids") or []),
        )
        change_request = {
            "artifact_type": "FailureBackedChangeRequest",
            "schema_version": "failure_backed_change_request.v1",
            "project": project.name,
            "project_dir": project.as_posix(),
            "project_stratum": project_stratum,
            "target": target,
            "authority": "failing_contract_test",
            "failure_signature": failure.get("failure_signature"),
            "failing_nodeids": list(failure.get("failing_nodeids") or []),
            "detail": str(failure.get("failure_summary") or "repeated project-native test failure"),
            "leaf_failure_summary": failure.get("leaf_failure_summary"),
            "failure_kind": failure_kind,
            "contract_failure_evidence": [{
                "target": target,
                "authority": "failing_contract_test",
                "detail": str(failure.get("failure_summary") or "repeated project-native test failure"),
                "leaf_failure_summary": failure.get("leaf_failure_summary"),
                "failure_kind": failure_kind,
                "failing_nodeids": list(failure.get("failing_nodeids") or []),
                "failure_signature": failure.get("failure_signature"),
            }],
            "source_digest": before,
            "repeat_count": repeat_count,
            "apply_source": False,
        }
    elif status == "qualified_failure" and not unchanged:
        status = "source_invariant_failed"
    return {
        "project": project.name,
        "project_dir": project.as_posix(),
        "project_stratum": project_stratum,
        "status": status,
        "target": target,
        "change_request": change_request,
        "repetitions": repetitions,
        "source_invariant": {"before": before, "after": after, "unchanged": unchanged},
    }

def _intake_work_root(root: Path, stamp: str, intake: dict[str, Any]) -> Path:
    configured = Path(str(intake.get("work_directory") or ".nfi"))
    base = configured if configured.is_absolute() else root / configured
    run_id = f"{stamp[9:15]}{stamp[-7:-1]}"
    return base / run_id

def _validated_test_targets(projects: list[Path], targets: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in targets:
        target = _normalize_nodeid(str(raw).strip())
        test_path = target.split("::", 1)[0]
        path = Path(test_path)
        if (
            not target
            or target.startswith("-")
            or path.is_absolute()
            or ".." in path.parts
            or path.suffix != ".py"
        ):
            raise ValueError(f"unsafe native pytest target: {raw}")
        if not all((project.resolve() / path).is_file() for project in projects):
            raise ValueError(f"native pytest target is missing from a project: {raw}")
        if target not in normalized:
            normalized.append(target)
    return normalized

def run_project_native_verification(
    *,
    root: Path,
    project: Path,
    failing_nodeids: list[str],
    policy: dict[str, Any] | None = None,
    project_version_hint: str | None = None,
) -> dict[str, Any]:
    policy = policy or load_project_development_policy()
    intake = dict(policy.get("native_failure_intake") or {})
    overlay = Path(str(intake.get("dependency_overlay") or ""))
    intake["dependency_overlay_path"] = ((root / overlay).resolve().as_posix() if str(overlay) else "")
    intake["project_dependency_overlay_paths"] = {
        str(name).lower(): (root / Path(str(path))).resolve().as_posix()
        for name, path in dict(intake.get("project_dependency_overlays") or {}).items()
    }
    _configure_short_basetemp(root, intake)
    intake = _project_specific_intake(project, intake)
    if project_version_hint:
        intake["project_version_hint"] = project_version_hint
    intake["shard_cache_enabled"] = False
    normalized = [_normalize_nodeid(str(value)) for value in failing_nodeids if value]
    targeted = _run_pytest(project.resolve(), intake, nodeids=normalized)
    regression_targets = [
        _normalize_nodeid(str(value))
        for value in intake.get("regression_targets") or []
        if value
    ]
    regression = _run_pytest(
        project.resolve(), intake, nodeids=regression_targets or None
    )
    targeted_passed = bool(normalized) and targeted.get("status") == "passed"
    regression_status = str(regression.get("status") or "")
    status = (
        "passed"
        if targeted_passed and regression_status == "passed"
        else "targeted_passed_regression_environment_blocked"
        if targeted_passed and regression_status == "environment_blocked"
        else "failed"
    )
    return {
        "artifact_type": "ProjectNativeVerificationResult",
        "status": status,
        "evidence_scope": "targeted_and_regression" if status == "passed" else "targeted_only" if targeted_passed else "none",
        "failing_nodeids": normalized,
        "targeted_replay": targeted,
        "regression_suite": regression,
        "authority": "project_native_pytest",
        "network_allowed": False,
    }
