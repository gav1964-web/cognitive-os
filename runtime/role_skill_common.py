"""Common helpers for typed role skills."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RoleSkillError(RuntimeError):
    """Raised when a role skill cannot run safely."""


def load_skill_registry(root: Path) -> dict[str, Any]:
    path = root / "registry" / "skills.json"
    if not path.exists():
        raise RoleSkillError(f"skill registry not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        raise RoleSkillError("skill registry must contain a skills list")
    return payload


def write_role_artifact(root: Path, role: str, artifact: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "roles" / role
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{artifact['artifact_type']}_{stamp}.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
