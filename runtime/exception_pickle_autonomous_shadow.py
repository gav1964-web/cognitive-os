"""Autonomous shadow run for exception pickle reconstruction candidates."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_constructor_samples import _sample_constructor_value
from .exception_pickle_semantic_replay import (
    _target_import_stub_modules,
    _verify_project_native_semantic_replay,
)
from .exception_pickle_source_samples import _sample_constructor_value_for_source_file
from .exception_pickle_holdout_transaction import (
    DEFAULT_AUDIT,
    DEFAULT_LEDGER,
    run_exception_pickle_holdout_transaction,
)
from .generated_stub_admission import inspect_generated_function_stubs
from .programmer_exception_pickle_patch import exception_pickle_reconstruction_patch


def run_exception_pickle_autonomous_shadow(
    *,
    root: Path,
    execution_dir: Path,
    ledger_path: Path = DEFAULT_LEDGER,
    audit_path: Path = DEFAULT_AUDIT,
) -> dict[str, Any]:
    """Prepare and statically verify one autonomous candidate in shadow mode."""
    root = root.resolve()
    holdout = run_exception_pickle_holdout_transaction(
        root=root,
        ledger_path=ledger_path,
        audit_path=audit_path,
        regression_passed=True,
        config_doctor_passed=True,
    )
    candidate = _select_candidate(holdout.get("holdout_candidates") or [])
    if candidate is None:
        return _blocked("no_applicable_holdout_candidate", holdout)
    audit = _read_json(root, audit_path)
    source_row = _audit_row_for_candidate(audit, candidate)
    if source_row is None:
        return _blocked("candidate_not_found_in_audit", holdout)
    project = root / str(source_row.get("project_root") or "")
    source_file = project / str(source_row.get("path") or "")
    before = hashlib.sha256(source_file.read_bytes()).hexdigest()
    sandbox = execution_dir / "sandbox_project"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    shutil.copytree(
        project,
        sandbox,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    sandbox_file = sandbox / str(source_row.get("path") or "")
    original = sandbox_file.read_text(encoding="utf-8")
    recipe = {
        "operator_id": "preserve_exception_constructor_reconstruction",
        "reconstruction_method": "__reduce__",
        "state_strategy": "reuse_direct_assignments",
        "required_constructor_inputs": list(source_row.get("required_constructor_parameters") or []),
    }
    patch = exception_pickle_reconstruction_patch(
        original,
        class_name=str(source_row.get("class_name") or ""),
        recipe=recipe,
    )
    if patch is None:
        return _blocked("strict_patch_synthesis_failed", holdout, candidate=candidate)
    sandbox_file.write_text(str(patch["source"]), encoding="utf-8")
    stub = inspect_generated_function_stubs(
        original_project=project,
        sandbox_project=sandbox,
        patch={
            "patches": [{
                "file": source_row.get("path"),
                "target": candidate.get("target"),
            }]
        },
    )
    changed = _changed_python_files(project, sandbox)
    checks = {
        "holdout_transaction_ready": holdout.get("status") == "holdout_ready",
        "patch_compiles": _compiles(str(patch["source"]), str(source_row.get("path") or "")),
        "single_file_scope": changed == [str(source_row.get("path") or "").replace("\\", "/")],
        "no_generated_function_stubs": stub.get("status") == "passed",
        "source_digest_unchanged": hashlib.sha256(source_file.read_bytes()).hexdigest() == before,
        "source_apply_forbidden": True,
        "kb_promotion_forbidden": True,
    }
    native_replay = (
        _verify_project_native_semantic_replay(
            sandbox=sandbox,
            source_row=source_row,
            state_attributes=list(patch["stored_inputs"]),
        )
        if all(checks.values())
        else {"status": "not_requested", "reason": "static_shadow_checks_failed"}
    )
    checks["project_native_semantic_replay"] = native_replay.get("status") == "passed"
    counted = all(checks.values())
    return {
        "artifact_type": "ExceptionPickleAutonomousShadowRun",
        "schema_version": "exception_pickle_autonomous_shadow_run.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "autonomous_verified_shadow" if counted else "blocked",
        "candidate": candidate,
        "operator_id": recipe["operator_id"],
        "sandbox_project": sandbox.as_posix(),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "stub_admission": stub,
        "project_native_semantic_replay": native_replay,
        "sandbox_changed_python_files": changed,
        "source_sha256": before,
        "source_apply": False,
        "kb_promotion": False,
        "counts_as_autonomous_verified_transformation": counted,
        "reason_not_counted": None
        if counted
        else "project-native semantic replay did not pass",
    }


def _select_candidate(candidates: list[Any]) -> dict[str, Any] | None:
    rows = [dict(row) for row in candidates if isinstance(row, dict)]
    rows.sort(key=lambda row: (-int(row.get("score") or 0), str(row.get("project")), str(row.get("target"))))
    return rows[0] if rows else None


def _audit_row_for_candidate(audit: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any] | None:
    for row in audit.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        target = f"{row.get('path')}:{row.get('class_name')}.__init__"
        project = row.get("canonical_project") or row.get("project")
        if project == candidate.get("project") and target == candidate.get("target"):
            return dict(row)
    return None


def _changed_python_files(original: Path, sandbox: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(sandbox.rglob("*.py")):
        if any(part in {".git", ".pytest_cache", "__pycache__", ".venv"} for part in path.parts):
            continue
        relative = path.relative_to(sandbox)
        peer = original / relative
        if not peer.is_file() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(peer.read_bytes()).digest():
            changed.append(relative.as_posix())
    return changed


def _compiles(source: str, filename: str) -> bool:
    try:
        compile(source, filename, "exec")
    except SyntaxError:
        return False
    return True



def _blocked(reason: str, holdout: dict[str, Any], *, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "artifact_type": "ExceptionPickleAutonomousShadowRun",
        "schema_version": "exception_pickle_autonomous_shadow_run.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "blocking_reason": reason,
        "candidate": candidate,
        "holdout_status": holdout.get("status"),
        "source_apply": False,
        "kb_promotion": False,
        "counts_as_autonomous_verified_transformation": False,
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
