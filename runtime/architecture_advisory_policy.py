"""Trust boundary for architecture synthesis advisory artifacts."""

from __future__ import annotations


def trusted_architecture_advisory(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("artifact_type") == "ProjectArchitectureSynthesis"
        and value.get("source") == "knowledge_backed_architecture_synthesis"
        and value.get("architect_consumable") is True
    )
