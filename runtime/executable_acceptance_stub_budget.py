"""Bound controlled dependency stubs by external package roots."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def stub_attempt_budget(policy: dict[str, Any]) -> int:
    roots = max(0, int(policy.get("max_missing_modules") or 0))
    namespaces = max(1, int(policy.get("max_namespace_modules_per_dependency") or 1))
    return max(1, roots * namespaces + 1)


def can_stub_missing(
    project_dir: Path,
    missing: str,
    policy: dict[str, Any],
    stubbed: list[str],
) -> bool:
    if not policy.get("enabled") or not policy.get("stub_external_missing_modules") or not missing:
        return False
    if missing in stubbed:
        return False
    top = missing.split(".", 1)[0]
    roots = {name.split(".", 1)[0] for name in stubbed}
    if top not in roots and len(roots) >= int(policy.get("max_missing_modules") or 0):
        return False
    return not (project_dir / top).exists() and not (project_dir / "src" / top).exists()
