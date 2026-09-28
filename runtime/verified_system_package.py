"""Stable facade for split `verified_system_package` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['verified_system_package_part1', 'verified_system_package_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['build_verified_system_package']
