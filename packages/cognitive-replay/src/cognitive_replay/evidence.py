"""Canonical digests and workspace-bounded paths."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any

class HistoricalEvidencePathError(ValueError):
    """Raised when historical evidence escapes the workspace."""


def inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HistoricalEvidencePathError("historical mining path escapes workspace") from exc
    return path


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "-", value.strip().lower()).strip("-")


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

