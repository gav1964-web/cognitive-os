"""Fill measured challenge shortages from revision-bound external projects."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .self_development_challenge_evidence import bounded_project_text, native_test_roots


def fill_external_shortage(
    *, root: Path, splits: list[dict[str, Any]],
    shortages: dict[str, dict[str, int]],
    acquisition_candidates: list[dict[str, Any]],
    holdout_candidates: list[dict[str, Any]], exposed_projects: set[str],
) -> list[dict[str, Any]]:
    used = []
    for split in splits:
        project_type = str(split["project_type"])
        for split_name, candidates in (
            ("holdout", holdout_candidates),
            ("acquisition", acquisition_candidates),
        ):
            needed = int(shortages[project_type][split_name])
            for raw in candidates:
                if needed <= 0:
                    break
                row = _external_row(
                    root=root, raw=raw, project_type=project_type,
                    split_name=split_name, exposed_projects=exposed_projects,
                )
                if not row or not _independent(row, split):
                    continue
                split[split_name].append(row)
                used.append(row)
                needed -= 1
            shortages[project_type][split_name] = needed
        split["checks"] = split_checks(split["acquisition"], split["holdout"])
    return used


def _external_row(
    *, root: Path, raw: dict[str, Any], project_type: str,
    split_name: str, exposed_projects: set[str],
) -> dict[str, Any] | None:
    project = str(raw.get("project") or "")
    if (
        raw.get("expected_project_type") != project_type
        or project.lower() in exposed_projects
    ):
        return None
    project_root = (root / str(raw.get("project_root") or "")).resolve()
    try:
        project_root.relative_to(root)
    except ValueError:
        return None
    git = _git_snapshot(project_root)
    revision = str(raw.get("revision") or "")
    source_url = str(raw.get("source_url") or "")
    tests = native_test_roots(project_root) if project_root.is_dir() else []
    if (
        not tests
        or git.get("revision") != revision
        or git.get("status") != ""
        or _normalized_origin(git.get("origin", "")) != _normalized_origin(source_url)
    ):
        return None
    digest = "sha256:" + hashlib.sha256(
        bounded_project_text(project_root).encode()
    ).hexdigest()
    return {
        **dict(raw),
        "canonical_project": project.lower(),
        "content_digest": digest,
        "source_kind": f"targeted_external_{split_name}",
        "acquisition_reason": f"measured_local_{split_name}_shortage",
        "native_test_roots": tests,
        "git_metadata_present": (project_root / ".git").exists(),
    }


def _independent(row: dict[str, Any], split: dict[str, Any]) -> bool:
    existing = [*split["holdout"], *split["acquisition"]]
    return (
        bool(row.get("owner"))
        and row["owner"] not in {item["owner"] for item in existing}
        and row["content_digest"] not in {item["content_digest"] for item in existing}
    )


def _git_snapshot(project: Path) -> dict[str, str]:
    if not (project / ".git").exists():
        return {}
    prefix = ["git", "-c", f"safe.directory={project.as_posix()}", "-C", str(project)]
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


def _normalized_origin(value: str) -> str:
    return value.strip().lower().removesuffix(".git").rstrip("/")


def split_checks(
    acquisition: list[dict[str, Any]], holdout: list[dict[str, Any]],
) -> dict[str, bool]:
    return {
        "owner_disjoint": {
            row["owner"] for row in acquisition
        }.isdisjoint(row["owner"] for row in holdout),
        "content_disjoint": {
            row["content_digest"] for row in acquisition
        }.isdisjoint(row["content_digest"] for row in holdout),
    }
