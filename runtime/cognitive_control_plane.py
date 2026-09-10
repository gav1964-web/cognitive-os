"""Stable facade for split `cognitive_control_plane` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['cognitive_control_plane_part1', 'cognitive_control_plane_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['run_cognitive_control_plane', 'run_prompt_product_control_plane']
