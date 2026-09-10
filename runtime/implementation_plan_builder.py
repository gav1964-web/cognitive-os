"""Stable facade for split `implementation_plan_builder` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['implementation_plan_builder_part1', 'implementation_plan_builder_part2', 'implementation_plan_builder_part3']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['build_implementation_plan']
