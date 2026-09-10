"""Content-addressed storage and verification for promoted evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "evidence_ledger_entry.v1"


class EvidenceLedgerError(ValueError):
    """Raised when promoted evidence cannot be trusted or reproduced."""


def promote_evidence(
    *,
    root: Path,
    source: Path,
    producer_fingerprint: str,
    evaluator_fingerprint: str,
    replay_command: list[str],
) -> dict[str, Any]:
    root = root.resolve()
    source = source.resolve()
    _require_inside(root, source)
    if not source.is_file():
        raise EvidenceLedgerError("evidence source must be a file")
    if not producer_fingerprint.strip() or not evaluator_fingerprint.strip():
        raise EvidenceLedgerError("producer and evaluator fingerprints are required")
    if producer_fingerprint == evaluator_fingerprint:
        raise EvidenceLedgerError("evaluator must be independent from producer")
    if not replay_command or not all(isinstance(item, str) and item.strip() for item in replay_command):
        raise EvidenceLedgerError("replay command must be a non-empty argv list")

    content_digest = _bytes_digest(source.read_bytes())
    suffix = source.suffix.lower() if source.suffix else ".bin"
    artifact = root / "evidence" / "artifacts" / f"{content_digest.removeprefix('sha256:')}{suffix}"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if artifact.is_file() and _bytes_digest(artifact.read_bytes()) != content_digest:
        raise EvidenceLedgerError("content-addressed artifact collision")
    if not artifact.exists():
        shutil.copyfile(source, artifact)

    body = {
        "schema_version": SCHEMA_VERSION,
        "status": "promoted",
        "source": source.relative_to(root).as_posix(),
        "artifact": artifact.relative_to(root).as_posix(),
        "content_sha256": content_digest,
        "producer_fingerprint": producer_fingerprint,
        "evaluator_fingerprint": evaluator_fingerprint,
        "replay_command": list(replay_command),
    }
    entry_digest = _canonical_digest(body)
    entry = {
        "artifact_type": "PromotedEvidenceLedgerEntry",
        "entry_digest": entry_digest,
        **body,
    }
    ledger_path = root / "evidence" / "ledger" / f"{entry_digest.removeprefix('sha256:')}.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if ledger_path.is_file() and ledger_path.read_bytes() != encoded:
        raise EvidenceLedgerError("ledger entry collision")
    ledger_path.write_bytes(encoded)
    return {**entry, "ledger_path": ledger_path.relative_to(root).as_posix()}


def verify_evidence_entry(*, root: Path, ledger_path: Path) -> dict[str, Any]:
    root = root.resolve()
    path = ledger_path if ledger_path.is_absolute() else root / ledger_path
    path = path.resolve()
    _require_inside(root / "evidence" / "ledger", path)
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _invalid(path, f"ledger_unreadable:{exc.__class__.__name__}")
    errors = _entry_errors(root=root, path=path, entry=entry)
    artifact = root / str(entry.get("artifact") or "")
    payload = _read_json_payload(artifact) if not errors else None
    return {
        "artifact_type": "PromotedEvidenceVerification",
        "status": "verified" if not errors else "invalid",
        "ledger_path": path.relative_to(root).as_posix(),
        "entry": entry,
        "evidence_payload": payload,
        "errors": errors,
    }


def _entry_errors(*, root: Path, path: Path, entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    body_keys = (
        "schema_version", "status", "source", "artifact", "content_sha256",
        "producer_fingerprint", "evaluator_fingerprint", "replay_command",
    )
    body = {key: entry.get(key) for key in body_keys}
    if entry.get("artifact_type") != "PromotedEvidenceLedgerEntry":
        errors.append("artifact_type_mismatch")
    if entry.get("schema_version") != SCHEMA_VERSION or entry.get("status") != "promoted":
        errors.append("schema_or_status_mismatch")
    expected_digest = _canonical_digest(body)
    if entry.get("entry_digest") != expected_digest:
        errors.append("entry_digest_mismatch")
    if path.stem != expected_digest.removeprefix("sha256:"):
        errors.append("ledger_filename_mismatch")
    producer = str(entry.get("producer_fingerprint") or "")
    evaluator = str(entry.get("evaluator_fingerprint") or "")
    if not producer or not evaluator or producer == evaluator:
        errors.append("independent_evaluator_missing")
    replay = entry.get("replay_command")
    if not isinstance(replay, list) or not replay or not all(isinstance(item, str) and item for item in replay):
        errors.append("replay_command_invalid")
    artifact = (root / str(entry.get("artifact") or "")).resolve()
    try:
        _require_inside(root / "evidence" / "artifacts", artifact)
    except EvidenceLedgerError:
        errors.append("artifact_outside_evidence_store")
        return errors
    if not artifact.is_file():
        errors.append("artifact_missing")
    elif _bytes_digest(artifact.read_bytes()) != entry.get("content_sha256"):
        errors.append("content_digest_mismatch")
    return errors


def _read_json_payload(path: Path) -> dict[str, Any] | None:
    if path.suffix.lower() != ".json":
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _invalid(path: Path, error: str) -> dict[str, Any]:
    return {
        "artifact_type": "PromotedEvidenceVerification",
        "status": "invalid",
        "ledger_path": path.as_posix(),
        "entry": {},
        "evidence_payload": None,
        "errors": [error],
    }


def _require_inside(parent: Path, child: Path) -> None:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError as exc:
        raise EvidenceLedgerError("path must stay inside the permitted workspace") from exc


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _bytes_digest(encoded)
