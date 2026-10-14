"""Generic runtime enforcement for declarative role safety policies."""

from __future__ import annotations

from typing import Any

from .role_directory import RoleDirectoryError, role_entry


class RoleRuntimePolicyError(RuntimeError):
    """Raised when a role artifact violates configured runtime authority."""


def enforce_role_runtime_policy(
    role_id: str,
    artifact: dict[str, Any],
    *,
    directory: dict[str, Any] | None = None,
) -> None:
    try:
        role = role_entry(role_id, directory=directory)
    except RoleDirectoryError:
        if directory is None:
            return
        raise
    source_policy = dict(role.get("policy") or {})
    llm_policy = dict(role.get("llm_policy") or {})
    kb_policy = dict(role.get("kb_policy") or {})
    violations = []
    if llm_policy.get("allowed") is False and _flag(
        artifact,
        ("llm_invoked",),
        ("architect_advisory", "llm_invoked"),
        ("safety", "llm_invoked"),
    ):
        violations.append("llm_invocation_forbidden")
    mutation_policy = str(source_policy.get("source_mutation") or "")
    if mutation_policy == "forbidden" and _flag(
        artifact,
        ("source_code_changes",),
        ("source_project_modified",),
        ("safety", "source_code_changes"),
    ):
        violations.append("source_mutation_forbidden")
    if kb_policy.get("auto_promote") is False and _flag(
        artifact,
        ("kb_auto_promoted",),
        ("auto_promoted",),
        ("kb_policy", "auto_promote"),
    ):
        violations.append("kb_auto_promotion_forbidden")
    if violations:
        raise RoleRuntimePolicyError(f"role runtime policy violation for {role_id}: {','.join(violations)}")


def _flag(payload: dict[str, Any], *paths: tuple[str, ...]) -> bool:
    for path in paths:
        value: Any = payload
        for part in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if value is True:
            return True
    return False
