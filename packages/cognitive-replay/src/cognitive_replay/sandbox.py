"""Reproduce a historical defect in an isolated local Git sandbox."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .evidence import evidence_digest, inside
from .git import _git, _git_snapshot
from .environment import prepare_environment
from .process import run_command as _run
from .pytest_report import (
    bounded_result as _bounded_result, pytest_status as _pytest_status, run_pytest,
)
from .metadata import _project_distribution_name
from .version import _project_version_hint


def qualify_candidate_in_sandbox(
    *, root: Path, public: dict[str, Any], oracle: dict[str, Any], timeout: int = 180,
    environment_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = inside(root, str(public.get("project_root") or ""))
    before = _git_snapshot(source)
    worktrees_before = _worktree_registry(source)
    sandbox_parent = root / ".nft" / "historical"
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    control = Path(tempfile.mkdtemp(prefix="q_", dir=sandbox_parent))
    sandbox = control / "source"
    result: dict[str, Any]
    try:
        if not before.get("revision") or before.get("status") != "":
            raise ValueError("source repository must have a clean readable snapshot")
        result = _run_candidate(
            root=root, control=control, source=source, sandbox=sandbox, public=public,
            oracle=oracle, timeout=timeout, profile=dict(environment_profile or {}),
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        detail = str(exc).strip().replace("\r", " ").replace("\n", " ")[:240]
        result = {
            "status": "environment_blocked",
            "reason": f"sandbox_preparation_failed:{type(exc).__name__}:{detail}",
            "baseline": {}, "fixed": {},
        }
    result["sandbox_cleaned"] = _cleanup(source, sandbox, control)
    try:
        control.resolve().relative_to(sandbox_parent.resolve())
        shutil.rmtree(control, onerror=_remove_readonly)
    except (OSError, ValueError):
        result["sandbox_cleaned"] = False
    after = _git_snapshot(source)
    worktrees_after = _worktree_registry(source)
    result["source_head_unchanged"] = before.get("revision") == after.get("revision")
    result["source_worktree_unchanged"] = before.get("status") == after.get("status") == ""
    result["source_worktree_registry_unchanged"] = worktrees_before == worktrees_after
    return result


def _run_candidate(
    *, root: Path, control: Path, source: Path, sandbox: Path, public: dict[str, Any],
    oracle: dict[str, Any], timeout: int, profile: dict[str, Any],
) -> dict[str, Any]:
    baseline = str(public["baseline_revision"])
    fix = str(oracle["fix_revision"])
    test_files = [str(value) for value in oracle.get("test_files") or []]
    test_entries = [str(value) for value in oracle.get("test_entry_files") or []]
    production = [str(value) for value in oracle.get("production_files") or []]
    checkout = _run(
        [
            "git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
            "worktree", "add", "--detach", "--quiet", str(sandbox), baseline,
        ],
        cwd=source, timeout=timeout,
    )
    if checkout["returncode"] != 0:
        detail = str(checkout.get("stderr") or checkout.get("stdout") or "").strip()[-500:]
        raise ValueError(f"baseline worktree failed:{detail}")
    python, bootstrap = prepare_environment(
        root=root, project=sandbox, directory=control / "environment", profile=profile, timeout=timeout,
    )
    bootstrap["project_metadata"] = _ensure_distribution_metadata(sandbox, source)
    bootstrap["environment_digest"] = evidence_digest({
        key: value for key, value in bootstrap.items() if key != "environment_digest"
    })
    test_patch = _git(source, ["diff", "--no-ext-diff", baseline, fix, "--", *test_files])
    if _sha256(test_patch) != oracle.get("test_patch_sha256"):
        raise ValueError("test patch digest mismatch")
    _apply_patch(sandbox, test_patch, "test.patch", timeout)
    def probe(phase: str) -> dict[str, Any]:
        return run_pytest(
            sandbox=sandbox, python=python, control=control, test_entries=test_entries,
            phase=phase, timeout=timeout, plugins=list(profile.get("pytest_plugins") or []),
        )

    baseline_run = probe("baseline-1")
    baseline_status = _pytest_status(baseline_run)
    if baseline_status != "reproducible_failure":
        return {
            "status": (
                "not_reproduced" if baseline_status == "passed" else "environment_blocked"
            ),
            "reason": f"baseline_{baseline_status}",
            "baseline": _bounded_result(baseline_run), "fixed": {},
            "test_patch_digest_verified": True,
            "environment_bootstrap": bootstrap,
        }
    repeated = probe("baseline-2")
    first_report, repeated_report = baseline_run["structured"], repeated["structured"]
    stable = (
        _pytest_status(repeated) == "reproducible_failure"
        and first_report["collected"] == repeated_report.get("collected")
        and first_report["failed"] == repeated_report.get("failed")
        and first_report["failure_signature"] == repeated_report.get("failure_signature")
    )
    common = {
        "baseline": _bounded_result(baseline_run),
        "baseline_repeats": [_bounded_result(baseline_run), _bounded_result(repeated)],
        "test_patch_digest_verified": True, "environment_bootstrap": bootstrap,
    }
    if not stable:
        return {**common, "status": "not_reproduced", "reason": "baseline_failure_not_repeatable",
                "fixed": {}, "comparison_checks": {"baseline_failure_repeatable": False}}
    production_patch = _git(
        source, ["diff", "--no-ext-diff", baseline, fix, "--", *production]
    )
    if _sha256(production_patch) != oracle.get("production_patch_sha256"):
        raise ValueError("production patch digest mismatch")
    _apply_patch(sandbox, production_patch, "production.patch", timeout)
    fixed_run = probe("fixed")
    fixed_status = _pytest_status(fixed_run)
    fixed_report = fixed_run["structured"]
    checks = {
        "baseline_failure_repeatable": stable,
        "collection_unchanged": first_report["collected"] == fixed_report.get("collected"),
        "all_baseline_failures_pass": set(first_report["failed"]).issubset(fixed_report.get("passed", [])),
        "fixed_suite_passed": fixed_status == "passed",
    }
    qualified = all(checks.values())
    return {
        **common,
        "status": "qualified" if qualified else "oracle_fix_not_verified",
        "reason": (
            "baseline_fails_and_upstream_fix_passes"
            if qualified else "upstream_fix_verification_failed"
        ),
        "fixed": _bounded_result(fixed_run), "comparison_checks": checks,
        "production_patch_digest_verified": True,
        "environment_bootstrap": bootstrap,
    }


def _apply_patch(sandbox: Path, patch: str, name: str, timeout: int) -> None:
    path = sandbox / f".cognitive_os_{name}"
    path.write_text(patch, encoding="utf-8")
    try:
        run = _run(
            ["git", "apply", "--whitespace=nowarn", str(path)], cwd=sandbox, timeout=timeout,
        )
        if run["returncode"] != 0:
            raise ValueError(f"{name} cannot be applied")
    finally:
        path.unlink(missing_ok=True)


def _ensure_distribution_metadata(sandbox: Path, identity_source: Path) -> dict[str, Any]:
    historical_name = _project_distribution_name(sandbox).strip()
    name = (
        _project_distribution_name(identity_source).strip()
        if historical_name == sandbox.name else historical_name
    )
    version = (_project_version_hint(sandbox) or "0.0.0").strip()
    normalized = re.sub(r"[-_.]+", "_", name)
    if not re.fullmatch(r"[A-Za-z0-9_]+", normalized) or not re.fullmatch(r"[A-Za-z0-9.+!_-]+", version):
        raise ValueError("project distribution metadata identity is invalid")
    directory = sandbox / f"{normalized}-{version}.dist-info"
    directory.mkdir(exist_ok=True)
    metadata = directory / "METADATA"
    metadata.write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    return {
        "status": "sandbox_distribution_metadata_created",
        "distribution": name, "version": version,
        "path": directory.relative_to(sandbox).as_posix(),
        "source_apply": False,
    }


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _worktree_registry(source: Path) -> str:
    try:
        return _git(source, ["worktree", "list", "--porcelain"])
    except ValueError:
        return ""


def _cleanup(source: Path, sandbox: Path, parent: Path) -> bool:
    try:
        sandbox.resolve().relative_to(parent.resolve())
        if (sandbox / ".git").exists():
            removal = _run(
                [
                    "git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
                    "worktree", "remove", "--force", str(sandbox),
                ],
                cwd=source, timeout=30,
            )
            if removal["returncode"] != 0 and sandbox.exists():
                shutil.rmtree(sandbox, onerror=_remove_readonly)
        elif sandbox.exists():
            shutil.rmtree(sandbox, onerror=_remove_readonly)
        return not sandbox.exists()
    except (OSError, ValueError):
        return False


def _remove_readonly(function: Any, path: str, _error: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)
