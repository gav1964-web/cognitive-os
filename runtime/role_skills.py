"""Generic role skill interpreter.

Role identities and capabilities live in config/role_directory.json.
This module intentionally exposes no role-specific run_* functions.
"""

from __future__ import annotations

from typing import Any

from .role_artifact_builder import build_configured_artifact
from .role_skill_common import RoleSkillError, load_skill_registry, write_role_artifact


def run_role_skill(role_id: str, **inputs: Any) -> dict[str, Any]:
    """Run a role by interpreting its role_directory entry."""

    return build_configured_artifact(role_id=role_id, **inputs)


__all__ = [
    "RoleSkillError",
    "load_skill_registry",
    "run_role_skill",
    "write_role_artifact",
]
