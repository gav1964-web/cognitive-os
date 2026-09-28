"""Stable facade for split `greenfield_stage2_templates` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['greenfield_stage2_templates_part1', 'greenfield_stage2_templates_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['has_case', 'acceptance_for', 'content_for_case', 'expected_artifacts_for_case']
