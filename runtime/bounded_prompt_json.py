"""Serialize bounded prompt evidence without producing truncated JSON."""

from __future__ import annotations

import json
from typing import Any


def bounded_prompt_json(payload: dict[str, Any], *, max_chars: int = 12000) -> str:
    if max_chars < 64:
        raise ValueError("max_chars must be at least 64")
    for string_limit, item_limit in (
        (4000, 12),
        (2400, 10),
        (1400, 8),
        (800, 6),
        (400, 4),
        (180, 3),
        (80, 2),
    ):
        text = json.dumps(
            _compact(payload, string_limit=string_limit, item_limit=item_limit),
            ensure_ascii=False,
            sort_keys=True,
        )
        if len(text) <= max_chars:
            return text
    return json.dumps(
        {"evidence_truncated": True, "top_level_keys": sorted(payload)[:20]},
        ensure_ascii=False,
        sort_keys=True,
    )


def _compact(value: Any, *, string_limit: int, item_limit: int) -> Any:
    if isinstance(value, str):
        if len(value) <= string_limit:
            return value
        return value[:string_limit] + "...[truncated]"
    if isinstance(value, dict):
        return {
            str(key): _compact(item, string_limit=string_limit, item_limit=item_limit)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        compacted = [
            _compact(item, string_limit=string_limit, item_limit=item_limit)
            for item in value[:item_limit]
        ]
        if len(value) > item_limit:
            compacted.append({"items_truncated": len(value) - item_limit})
        return compacted
    return value
