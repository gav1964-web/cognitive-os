"""Stable facade for split `greenfield_web_research_fastapi_template` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['greenfield_web_research_fastapi_template_part1', 'greenfield_web_research_fastapi_template_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['expected_artifacts', 'acceptance_for', 'content_for']
