"""Atomic checkpoints for sealed foundation transfer exams."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "foundation_transfer_checkpoint.v1"


def checkpoint_path(corpus: Path) -> Path:
    return corpus / "transfer_exam_checkpoint.json"


def load_checkpoint(corpus: Path, manifest_path: Path) -> dict[str, Any]:
    path = checkpoint_path(corpus)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("transfer exam checkpoint schema mismatch")
    if payload.get("manifest_sha256") != file_digest(manifest_path):
        raise RuntimeError("transfer exam checkpoint manifest mismatch")
    return payload


def save_checkpoint(
    corpus: Path, manifest_path: Path, *, stage: str,
    promotion_snapshot_sha256: str, reports: dict[str, dict[str, Any]],
    resume_allowed: bool = True, reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    references = {
        key: report_reference(value) for key, value in reports.items() if value
    }
    payload = {
        "artifact_type": "FoundationTransferExamCheckpoint",
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "manifest_sha256": file_digest(manifest_path),
        "promotion_snapshot_sha256": promotion_snapshot_sha256,
        "resume_allowed": resume_allowed,
        "reports": references,
        **dict(metadata or {}),
        **({"reason": reason} if reason else {}),
    }
    _atomic_json(checkpoint_path(corpus), payload)
    return payload


def load_reports(checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reports = {}
    for key, value in dict(checkpoint.get("reports") or {}).items():
        reference = dict(value or {})
        path = Path(str(reference.get("path") or ""))
        if not path.is_file() or file_digest(path) != reference.get("sha256"):
            raise RuntimeError(f"transfer exam checkpoint report changed: {key}")
        reports[key] = json.loads(path.read_text(encoding="utf-8"))
    return reports


def report_reference(report: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(report.get("report_path") or ""))
    if not path.is_file():
        raise RuntimeError("checkpointed transfer report path is missing")
    return {"path": path.as_posix(), "sha256": file_digest(path)}


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False,
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
