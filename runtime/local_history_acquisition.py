"""Deepen selected local snapshots without changing their checked-out source."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .local_historical_defect_evidence import evidence_digest, inside
from .local_historical_defect_mining import (
    HistoricalDefectMiningError,
    TARGET_TYPES,
    _git,
    _git_snapshot,
)


ALLOWED_ORIGIN_HOSTS = {"github.com", "gitlab.com"}


class LocalHistoryAcquisitionError(ValueError):
    """Raised when a history acquisition request violates its boundary."""


def acquire_local_history(
    *, root: Path, manifest: dict[str, Any], per_type: int = 6,
    deepen: int = 160, project_types: tuple[str, ...] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    base = root.resolve()
    selected_types = project_types or TARGET_TYPES
    _validate_request(
        manifest, per_type=per_type, deepen=deepen, project_types=selected_types,
    )
    suggestions = dict(dict(manifest["network_fallback"])["suggested_sources"])
    selected = [
        dict(row) for project_type in selected_types
        for row in list(suggestions.get(project_type) or [])[:per_type]
    ]
    if selected and not _owners_independent(selected):
        raise LocalHistoryAcquisitionError("history acquisition owners must be independent")
    if any(not _origin_allowed(str(row.get("source_url") or "")) for row in selected):
        raise LocalHistoryAcquisitionError("history acquisition origin is not allowed")
    projects = [inside(base, str(row.get("project_root") or "")) for row in selected]
    if len(projects) != len(set(projects)):
        raise LocalHistoryAcquisitionError("history acquisition projects must be unique")
    results = [_acquire_one(base, row, deepen=deepen) for row in selected]
    acquired = sum(row["status"] == "acquired" for row in results)
    failed = len(results) - acquired
    checks = {
        "public_shortage_manifest": manifest.get("status") == "shortage",
        "network_fallback_required": dict(manifest.get("network_fallback") or {}).get("required") is True,
        "owner_independent": _owners_independent(selected),
        "only_allowed_origins": all(_origin_allowed(str(row.get("source_url") or "")) for row in selected),
        "head_revisions_unchanged": all(row.get("head_unchanged") is True for row in results),
        "worktrees_unchanged": all(row.get("worktree_unchanged") is True for row in results),
        "no_source_apply": True,
        "no_automatic_promotion": True,
    }
    status = (
        "completed" if selected and not failed and all(checks.values())
        else "completed_with_failures" if acquired
        else "blocked"
    )
    body = {
        "artifact_type": "LocalHistoryAcquisitionReceipt",
        "schema_version": "local_history_acquisition_receipt.v1",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest_digest": manifest.get("manifest_digest"),
        "request": {
            "per_type": per_type, "deepen": deepen,
            "project_types": list(selected_types), "selected": len(selected),
        },
        "summary": {"selected": len(selected), "acquired": acquired, "failed": failed},
        "results": results,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "safety": {"source_apply": False, "automatic_promotion": False},
    }
    body["receipt_digest"] = evidence_digest(body)
    if write:
        body["report_path"] = _write_report(base, body).relative_to(base).as_posix()
    return body


def _acquire_one(root: Path, source: dict[str, Any], *, deepen: int) -> dict[str, Any]:
    project = inside(root, str(source.get("project_root") or ""))
    before = _git_snapshot(project) if project.is_dir() else {}
    expected_revision = str(source.get("snapshot_revision") or "")
    expected_origin = str(source.get("source_url") or "")
    admission = {
        "project_exists": project.is_dir(),
        "git_metadata_present": (project / ".git").exists(),
        "worktree_clean": before.get("status") == "",
        "head_matches_snapshot": before.get("revision") == expected_revision,
        "origin_matches_manifest": _normalized_origin(str(before.get("origin") or ""))
        == _normalized_origin(expected_origin),
        "origin_allowed": _origin_allowed(expected_origin),
        "history_is_missing": int(before.get("history_count") or 0) < 2,
    }
    base_result = {
        "project": source.get("project"),
        "project_stratum": source.get("project_stratum"),
        "owner": source.get("owner"),
        "project_root": source.get("project_root"),
        "source_url": expected_origin,
        "before_revision": before.get("revision"),
        "before_history_count": int(before.get("history_count") or 0),
        "admission": admission,
    }
    if not all(admission.values()):
        return {
            **base_result, "status": "blocked", "reason": "acquisition_admission_failed",
            "head_unchanged": before.get("revision") == expected_revision,
            "worktree_unchanged": before.get("status") == "",
        }
    try:
        _git(
            project,
            ["fetch", f"--deepen={deepen}", "--filter=blob:none", "origin"],
            timeout=180,
        )
    except HistoricalDefectMiningError:
        after = _git_snapshot(project)
        return {
            **base_result, "status": "failed", "reason": "git_fetch_failed",
            "after_revision": after.get("revision"),
            "after_history_count": int(after.get("history_count") or 0),
            "head_unchanged": after.get("revision") == before.get("revision"),
            "worktree_unchanged": before.get("status") == after.get("status") == "",
        }
    after = _git_snapshot(project)
    head_unchanged = after.get("revision") == before.get("revision")
    worktree_unchanged = before.get("status") == after.get("status") == ""
    history_increased = int(after.get("history_count") or 0) > int(before.get("history_count") or 0)
    return {
        **base_result,
        "status": "acquired" if head_unchanged and worktree_unchanged and history_increased else "failed",
        "reason": "history_deepened" if history_increased else "history_not_increased",
        "after_revision": after.get("revision"),
        "after_history_count": int(after.get("history_count") or 0),
        "history_increased": history_increased,
        "head_unchanged": head_unchanged,
        "worktree_unchanged": worktree_unchanged,
    }


def _validate_request(
    manifest: dict[str, Any], *, per_type: int, deepen: int,
    project_types: tuple[str, ...],
) -> None:
    if manifest.get("schema_version") != "local_historical_defect_public_manifest.v1":
        raise LocalHistoryAcquisitionError("history acquisition manifest schema mismatch")
    body = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    if evidence_digest(body) != manifest.get("manifest_digest"):
        raise LocalHistoryAcquisitionError("history acquisition manifest digest mismatch")
    fallback = dict(manifest.get("network_fallback") or {})
    if manifest.get("status") != "shortage" or fallback.get("required") is not True:
        raise LocalHistoryAcquisitionError("history acquisition requires a measured local shortage")
    selection_checks = {
        name: passed for name, passed in dict(manifest.get("checks") or {}).items()
        if name != "minimum_candidates_met"
    }
    if not selection_checks or not all(value is True for value in selection_checks.values()):
        raise LocalHistoryAcquisitionError("history acquisition selection checks failed")
    if not 1 <= per_type <= 12 or not 2 <= deepen <= 1000:
        raise LocalHistoryAcquisitionError("history acquisition request exceeds bounded limits")
    if not project_types or any(value not in TARGET_TYPES for value in project_types):
        raise LocalHistoryAcquisitionError("history acquisition project type is invalid")
    if len(project_types) != len(set(project_types)):
        raise LocalHistoryAcquisitionError("history acquisition project types must be unique")
    suggestions = dict(fallback.get("suggested_sources") or {})
    if any(
        row.get("project_stratum") != project_type
        for project_type in project_types for row in suggestions.get(project_type) or []
    ):
        raise LocalHistoryAcquisitionError("history acquisition source stratum mismatch")
    if any("fix_revision" in row for rows in dict(fallback.get("suggested_sources") or {}).values() for row in rows):
        raise LocalHistoryAcquisitionError("public acquisition manifest discloses a fix oracle")


def _origin_allowed(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_ORIGIN_HOSTS


def _normalized_origin(value: str) -> str:
    return value.strip().lower().removesuffix(".git").rstrip("/")


def _owners_independent(rows: list[dict[str, Any]]) -> bool:
    for project_type in TARGET_TYPES:
        owners = [
            str(row.get("owner") or "") for row in rows
            if row.get("project_stratum") == project_type
        ]
        if len(owners) != len(set(owners)) or not all(owners):
            return False
    return bool(rows)


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development" / "historical_defect_mining"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"history_acquisition_{stamp}.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
