"""Incrementally collect new ProjectDevelopmentRun evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .self_development_prospective_detection import run_prospective_detection


CHECKPOINT = "artifacts/self_development/prospective_collector_checkpoint.json"


class SelfDevelopmentCollectorError(ValueError):
    """Raised when a collector input is outside its bounded contract."""


def collect_project_development_report(*, root: Path, report_path: Path) -> dict[str, Any]:
    base = root.resolve()
    source = report_path.resolve()
    expected = (base / "artifacts" / "project_development").resolve()
    if source.parent != expected or not source.is_file():
        raise SelfDevelopmentCollectorError("collector accepts project-development reports only")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("artifact_type") != "ProjectDevelopmentRun":
        raise SelfDevelopmentCollectorError("collector source must be ProjectDevelopmentRun")
    relative = source.relative_to(base).as_posix()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    checkpoint_path = base / CHECKPOINT
    checkpoint = _load_checkpoint(checkpoint_path)
    processed = dict(checkpoint.get("processed") or {})
    if dict(processed.get(relative) or {}).get("sha256") == digest:
        return {
            "artifact_type": "SelfDevelopmentProspectiveCollectorReceipt",
            "status": "duplicate_ignored",
            "source": relative,
            "source_sha256": digest,
            "checkpoint": CHECKPOINT,
            "detector_run": False,
            "promotion_applied": False,
        }
    detection = run_prospective_detection(root=base, write=True)
    processed[relative] = {
        "sha256": digest,
        "generated_at": payload.get("generated_at"),
        "project": payload.get("project"),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    next_checkpoint = {
        "artifact_type": "SelfDevelopmentProspectiveCollectorCheckpoint",
        "schema_version": "self_development_prospective_collector_checkpoint.v1",
        "processed": dict(sorted(processed.items())),
        "last_detection": {
            "status": detection.get("status"),
            "candidate_count": detection.get("candidate_count"),
            "report_path": detection.get("report_path"),
        },
        "safety": {"source_apply": False, "promotion_applied": False},
    }
    _atomic_json_write(checkpoint_path, next_checkpoint)
    return {
        "artifact_type": "SelfDevelopmentProspectiveCollectorReceipt",
        "status": "candidate_detected" if detection.get("candidate_count") else "collected",
        "source": relative,
        "source_sha256": digest,
        "checkpoint": CHECKPOINT,
        "detector_run": True,
        "detection_status": detection.get("status"),
        "candidate_count": detection.get("candidate_count"),
        "detection_report_path": detection.get("report_path"),
        "promotion_applied": False,
    }


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"processed": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_prospective_collector_checkpoint.v1":
        raise SelfDevelopmentCollectorError("collector checkpoint schema mismatch")
    return payload


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
