"""Execute one design-authorized repair in an isolated project copy."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .generated_stub_admission import inspect_generated_function_stubs
from .programmer_exception_pickle_patch import exception_pickle_reconstruction_patch
from .project_development_experiment import _project_digest
from .project_native_failure_intake import (
    _copy_git_build_metadata,
    _project_version_hint,
    run_project_native_verification,
)


def run_authorized_implementation(
    *,
    root: Path,
    project_dir: Path,
    execution_dir: Path,
    design: dict[str, Any],
    authorization_validation: dict[str, Any],
    failing_nodeids: list[str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    target = str(design.get("target") or "")
    path_text, separator, symbol = target.partition(":")
    class_name, dot, constructor_name = symbol.rpartition(".")
    before = _project_digest(project_dir)
    authorization_policy = _authorization_policy(policy)
    implementation_recipe, recipe_authorized = _implementation_recipe(
        design, authorization_policy
    )
    original_source_path = (project_dir / path_text).resolve()
    try:
        original_source_path.relative_to(project_dir.resolve())
        target_inside_project = True
    except ValueError:
        target_inside_project = False
    target_file_exists = target_inside_project and original_source_path.is_file()
    target_source_sha256 = (
        hashlib.sha256(original_source_path.read_bytes()).hexdigest()
        if target_file_exists else None
    )
    prechecks = {
        "authorization_is_approved": authorization_validation.get("status") == "approved"
        and authorization_validation.get("sandbox_implementation_authorized") is True,
        "source_apply_is_forbidden": authorization_validation.get("source_apply_authorized") is False,
        "target_is_inside_project": target_inside_project,
        "target_file_exists": target_file_exists,
        "source_snapshot_matches_design": target_source_sha256 == design.get("source_sha256"),
        "single_python_target": bool(separator and dot and path_text.endswith(".py")),
        "constructor_target_is_supported": constructor_name == "__init__" and bool(class_name),
        "hypothesis_kind_is_supported": design.get("hypothesis_kind")
        == authorization_policy.get("required_hypothesis_kind"),
        "implementation_recipe_is_authorized": recipe_authorized,
        "failing_nodeids_are_present": bool(failing_nodeids),
    }
    if not all(prechecks.values()):
        return _blocked_result(target, prechecks, before)

    sandbox = execution_dir / "sandbox_project"
    shutil.copytree(
        project_dir,
        sandbox,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    _copy_git_build_metadata(
        project_dir,
        sandbox,
        dict(policy.get("native_failure_intake") or {}),
    )
    source_path = (sandbox / path_text).resolve()
    try:
        source_path.relative_to(sandbox.resolve())
    except ValueError:
        prechecks["target_is_inside_sandbox"] = False
        return _blocked_result(target, prechecks, before)
    if not source_path.is_file():
        prechecks["target_file_exists"] = False
        return _blocked_result(target, prechecks, before)

    original = source_path.read_text(encoding="utf-8")
    patch = exception_pickle_reconstruction_patch(
        original,
        class_name=class_name,
        constructor_name=constructor_name,
        recipe=implementation_recipe,
    )
    if patch is None:
        prechecks["strict_reducer_pattern_is_proven"] = False
        return _blocked_result(target, prechecks, before, sandbox=sandbox)
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    patch_artifact = {
        "artifact_type": "PatchPackage",
        "status": "prepared",
        "patches": [{
            "artifact_type": "PatchOperation",
            "kind": implementation_recipe.get("operator_id"),
            "target": target,
            "file": path_text,
            "stored_inputs": list(patch["stored_inputs"]),
            "reconstruction_method": patch["reconstruction_method"],
            "state_strategy": patch["state_strategy"],
            "diff": "".join(difflib.unified_diff(
                original.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=f"a/{path_text}",
                tofile=f"b/{path_text}",
            )),
        }],
        "sandbox_project": sandbox.as_posix(),
        "source_code_changes": False,
        "source_apply_allowed": False,
    }
    stub_admission = inspect_generated_function_stubs(
        original_project=project_dir,
        sandbox_project=sandbox,
        patch=patch_artifact,
    )
    changed_before_verification = _changed_python_files(project_dir, sandbox)
    verification = (
        run_project_native_verification(
            root=root,
            project=sandbox,
            failing_nodeids=failing_nodeids,
            policy=policy,
            project_version_hint=_project_version_hint(project_dir),
        )
        if stub_admission.get("status") == "passed"
        and changed_before_verification == [path_text.replace("\\", "/")]
        else {
            "artifact_type": "ProjectNativeVerificationResult",
            "status": "not_requested",
            "reason": "stub_or_scope_admission_blocked",
        }
    )
    semantic_verification = _verify_semantic_acceptance(sandbox, design)
    generated_build_files = _remove_generated_build_files(
        project_dir, sandbox, changed_before_verification
    )
    after = _project_digest(project_dir)
    changed_after_verification = _changed_python_files(project_dir, sandbox)
    checks = {
        **prechecks,
        "strict_reducer_pattern_is_proven": True,
        "patch_compiles": _compiles(patched, path_text),
        "no_generated_function_stubs": stub_admission.get("status") == "passed",
        "sandbox_scope_is_single_file": changed_before_verification
        == [path_text.replace("\\", "/")],
        "targeted_verification_passed": dict(verification.get("targeted_replay") or {}).get("status")
        == "passed",
        "regression_verification_passed": dict(verification.get("regression_suite") or {}).get("status")
        == "passed",
        "semantic_acceptance_passed": semantic_verification.get("status")
        in {"passed", "not_required"},
        "verification_did_not_widen_python_scope": changed_after_verification
        == [path_text.replace("\\", "/")],
        "original_source_snapshot_unchanged": before == after,
        "source_apply_remains_forbidden": True,
        "memory_promotion_remains_forbidden": True,
    }
    verified = all(checks.values())
    return {
        "artifact_type": "ProjectDevelopmentAuthorizedImplementationResult",
        "status": "verified_in_sandbox" if verified else "verification_failed",
        "target": target,
        "operator_id": implementation_recipe.get("operator_id"),
        "sandbox_project": sandbox.as_posix(),
        "patch_package": patch_artifact,
        "stub_admission": stub_admission,
        "project_native_verification": verification,
        "semantic_verification": semantic_verification,
        "generated_build_files_removed": generated_build_files,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "source_invariant": {"before": before, "after": after, "unchanged": before == after},
        "sandbox_changed_python_files": changed_after_verification,
        "source_apply": False,
        "memory_promotion": False,
    }


def _blocked_result(
    target: str, checks: dict[str, bool], before: str, *, sandbox: Path | None = None
) -> dict[str, Any]:
    return {
        "artifact_type": "ProjectDevelopmentAuthorizedImplementationResult",
        "status": "blocked",
        "target": target,
        "operator_id": "preserve_exception_constructor_reconstruction",
        "sandbox_project": sandbox.as_posix() if sandbox else None,
        "patch_package": None,
        "stub_admission": None,
        "project_native_verification": None,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "source_invariant": {"before": before, "after": before, "unchanged": True},
        "sandbox_changed_python_files": [],
        "source_apply": False,
        "memory_promotion": False,
    }


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


def _verify_semantic_acceptance(sandbox: Path, design: dict[str, Any]) -> dict[str, Any]:
    acceptance = design.get("semantic_acceptance")
    if acceptance is None:
        return {"status": "not_required"}
    if not isinstance(acceptance, dict):
        return {"status": "blocked", "reason": "invalid_semantic_acceptance"}
    target_path, _, symbol = str(design.get("target") or "").partition(":")
    class_name = symbol.split(".", 1)[0]
    module_path = target_path.removeprefix("src/").removesuffix(".py")
    if module_path.endswith("/__init__"):
        module_path = module_path[: -len("/__init__")]
    module_name = module_path.replace("/", ".").replace("\\", ".")
    constructor_args = acceptance.get("constructor_args")
    attributes = acceptance.get("state_attributes")
    expected_message = acceptance.get("expected_message")
    if not (
        module_name
        and class_name.isidentifier()
        and isinstance(constructor_args, list)
        and isinstance(attributes, list)
        and len(attributes) <= 8
        and all(isinstance(value, str) and value.isidentifier() for value in attributes)
        and isinstance(expected_message, str)
    ):
        return {"status": "blocked", "reason": "unsafe_semantic_acceptance_shape"}
    python = sandbox.parent / ("probe_env/Scripts/python.exe" if os.name == "nt" else "probe_env/bin/python")
    if not python.is_file():
        return {"status": "blocked", "reason": "verification_interpreter_missing"}
    payload = json.dumps({
        "module": module_name,
        "class_name": class_name,
        "constructor_args": constructor_args,
        "attributes": attributes,
        "expected_message": expected_message,
    }, ensure_ascii=True, separators=(",", ":"))
    script = (
        "import importlib,json,pickle,sys;"
        "p=json.loads(sys.argv[1]);"
        "c=getattr(importlib.import_module(p['module']),p['class_name']);"
        "x=c(*p['constructor_args']);y=pickle.loads(pickle.dumps(x));"
        "ok=(type(y) is type(x) and str(x)==str(y)==p['expected_message'] and "
        "all(getattr(x,a)==getattr(y,a) for a in p['attributes']));"
        "print(json.dumps({'ok':ok,'before':str(x),'after':str(y)}));"
        "raise SystemExit(0 if ok else 1)"
    )
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        completed = subprocess.run(
            [str(python), "-c", script, payload],
            cwd=sandbox,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "blocked", "reason": type(exc).__name__}
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "output": (completed.stdout or "").strip()[-2000:],
        "module": module_name,
        "class_name": class_name,
        "state_attributes": attributes,
    }


def _remove_generated_build_files(
    original: Path, sandbox: Path, changed_before_verification: list[str]
) -> list[str]:
    removed: list[str] = []
    protected = set(changed_before_verification)
    sandbox_build_lib = sandbox / "build" / "lib"
    original_build_lib = original / "build" / "lib"
    if sandbox_build_lib.is_dir() and not original_build_lib.exists():
        removed.extend(
            path.relative_to(sandbox).as_posix()
            for path in sorted(sandbox_build_lib.rglob("*.py"))
        )
        shutil.rmtree(sandbox_build_lib)
        build_dir = sandbox / "build"
        try:
            if build_dir.is_dir() and not any(build_dir.iterdir()):
                build_dir.rmdir()
        except OSError:
            pass
    for path in sorted(sandbox.rglob("_version.py")):
        relative = path.relative_to(sandbox).as_posix()
        peer = original / relative
        if relative in protected or peer.exists():
            continue
        try:
            prefix = path.read_text(encoding="utf-8", errors="replace")[:300].lower()
        except OSError:
            continue
        if "generated by" not in prefix or "don't track" not in prefix:
            continue
        path.unlink()
        removed.append(relative)
    return removed


def _authorization_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    experiment = dict(revision.get("bounded_experiment") or {})
    approval = dict(experiment.get("human_approval") or {})
    design = dict(approval.get("implementation_design") or {})
    return dict(design.get("implementation_authorization") or {})


def _implementation_recipe(
    design: dict[str, Any], authorization_policy: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    supplied = design.get("implementation_recipe")
    if supplied is None:
        return dict(authorization_policy), True
    if not isinstance(supplied, dict):
        return {}, False
    recipe = dict(supplied)
    inputs = recipe.get("required_constructor_inputs")
    allowed_strategies = set(authorization_policy.get("allowed_state_strategies") or [])
    maximum = int(authorization_policy.get("maximum_constructor_inputs") or 0)
    valid_inputs = (
        isinstance(inputs, list)
        and 0 < len(inputs) <= maximum
        and all(isinstance(value, str) and value.isidentifier() for value in inputs)
        and len(set(inputs)) == len(inputs)
    )
    checks = [
        recipe.get("operator_id") == authorization_policy.get("operator_id"),
        recipe.get("reconstruction_method") == authorization_policy.get("reconstruction_method"),
        recipe.get("state_strategy") in allowed_strategies,
        valid_inputs,
        recipe.get("state_strategy") == "reuse_direct_assignments",
    ]
    return recipe, all(checks)
