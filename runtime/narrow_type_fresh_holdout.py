"""Validate a frozen, project-level narrow-role holdout before execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .self_development_challenge_evidence import exposed_projects


REQUIRED_STRATA = ("cli_local_tool", "library_pure_transform")
REQUIRED_INVARIANTS = (
    "two_projects_per_stratum",
    "distinct_source_owners",
    "content_disjoint",
    "clean_git_worktrees",
    "exact_revisions_bound",
    "native_tests_present",
    "project_development_unexposed_at_freeze",
    "native_failure_unexposed_at_freeze",
    "holdout_frozen_before_execution",
    "source_apply",
    "knowledge_updates_before_evaluation",
    "automatic_promotion",
)


class FreshHoldoutError(ValueError):
    """Raised when a holdout manifest cannot be evaluated safely."""


def validate_fresh_holdout_manifest(
    *, root: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    base = root.resolve()
    cases = [dict(row) for row in manifest.get("cases") or [] if isinstance(row, dict)]
    snapshots = [_case_snapshot(base, row) for row in cases]
    owners = [str(row.get("source_owner") or "").lower() for row in cases]
    digests = [str(row.get("content_digest") or "") for row in cases]
    project_development_exposed = exposed_projects(
        base, "artifacts/project_development/project_development_*.json"
    )
    native_failure_exposed = exposed_projects(
        base, "artifacts/field_trials/project_native_failure_intake_*.json"
    )
    source_manifest = _source_manifest(base, manifest)
    invariants = dict(manifest.get("invariants") or {})
    checks = {
        "schema_valid": manifest.get("schema_version") == "narrow_type_fresh_holdout.v1",
        "manifest_frozen": manifest.get("status") == "frozen"
        and manifest.get("holdout_consumed") is False,
        "required_invariants_declared": all(
            invariants.get(name) is (False if name in {
                "source_apply", "knowledge_updates_before_evaluation", "automatic_promotion"
            } else True)
            for name in REQUIRED_INVARIANTS
        ),
        "two_projects_per_stratum": all(
            sum(row.get("project_stratum") == stratum for row in cases) == 2
            for stratum in REQUIRED_STRATA
        ) and len(cases) == 4,
        "distinct_source_owners": len(owners) == len(set(owners)) and all(owners),
        "content_disjoint": len(digests) == len(set(digests))
        and all(value.startswith("sha256:") and len(value) == 71 for value in digests),
        "project_roots_confined": all(row["root_confined"] for row in snapshots),
        "native_tests_present": all(row["native_tests_present"] for row in snapshots),
        "git_metadata_present": all(row["git_metadata_present"] for row in snapshots),
        "clean_git_worktrees": all(row["git_clean"] for row in snapshots),
        "exact_revisions_bound": all(row["revision_matches"] for row in snapshots),
        "origins_bound": all(row["origin_matches"] for row in snapshots),
        "project_development_unexposed": all(
            str(row.get("project") or "").lower() not in project_development_exposed
            for row in cases
        ),
        "native_failure_unexposed": all(
            str(row.get("project") or "").lower() not in native_failure_exposed
            for row in cases
        ),
        "source_challenge_manifest_bound": bool(source_manifest)
        and source_manifest.get("manifest_digest")
        == manifest.get("source_challenge_manifest_digest")
        and all(
            int(dict(source_manifest.get("shortages") or {}).get(stratum, {}).get("holdout") or 0) == 0
            for stratum in REQUIRED_STRATA
        ),
    }
    body = {
        "artifact_type": "NarrowTypeFreshHoldoutPreflight",
        "schema_version": "narrow_type_fresh_holdout_preflight.v1",
        "status": "ready" if all(checks.values()) else "blocked",
        "evaluation_split": manifest.get("evaluation_split"),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "case_snapshots": snapshots,
        "source_challenge_manifest": manifest.get("source_challenge_manifest"),
        "holdout_consumed": False,
        "source_apply": False,
        "automatic_promotion": False,
    }
    return {**body, "evidence_digest": _digest(body)}


def _case_snapshot(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    path, confined = _confined_path(root, str(case.get("project_root") or ""))
    tests = [str(value) for value in case.get("native_test_roots") or []]
    git = _git_snapshot(path) if confined and path.is_dir() else {}
    return {
        "project": case.get("project"),
        "project_stratum": case.get("project_stratum"),
        "project_root": case.get("project_root"),
        "root_confined": confined and path.is_dir(),
        "native_tests_present": bool(tests) and all((path / value).exists() for value in tests),
        "git_metadata_present": (path / ".git").exists(),
        "git_clean": git.get("status") == "",
        "observed_revision": git.get("revision"),
        "revision_matches": git.get("revision") == case.get("revision"),
        "observed_origin": git.get("origin"),
        "origin_matches": _normalized_origin(str(git.get("origin") or ""))
        == _normalized_origin(str(case.get("source_url") or "")),
    }


def _git_snapshot(project: Path) -> dict[str, str]:
    safe = project.as_posix()
    prefix = ["git", "-c", f"safe.directory={safe}", "-C", str(project)]
    values = {}
    for name, args in (
        ("status", ["status", "--porcelain=v1"]),
        ("revision", ["rev-parse", "HEAD"]),
        ("origin", ["remote", "get-url", "origin"]),
    ):
        try:
            run = subprocess.run(
                [*prefix, *args], capture_output=True, text=True,
                timeout=15, check=False, shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {}
        if run.returncode != 0:
            return {}
        values[name] = run.stdout.strip()
    return values


def _source_manifest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    path, confined = _confined_path(root, str(manifest.get("source_challenge_manifest") or ""))
    if not confined or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _confined_path(root: Path, value: str) -> tuple[Path, bool]:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return path, False
    return path, bool(value)


def _normalized_origin(value: str) -> str:
    return value.strip().lower().removesuffix(".git").rstrip("/")


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
