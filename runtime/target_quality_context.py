"""Structural context helpers for target-quality profile matching."""

from __future__ import annotations

from typing import Any


def owner_qualified_target(
    target: str, structural_evidence: dict[str, Any] | None
) -> str:
    owner = str(dict(structural_evidence or {}).get("owner_class") or "").strip()
    path, separator, symbol = target.partition(":")
    if not owner or not separator or "." in symbol:
        return target
    return f"{path}:{owner}.{symbol}"
