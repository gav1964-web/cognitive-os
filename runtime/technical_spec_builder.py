"""Stable facade for split `technical_spec_builder` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['technical_spec_builder_part1', 'technical_spec_builder_part2', 'technical_spec_builder_part3', 'technical_spec_builder_part4', 'technical_spec_builder_part5']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['build_technical_spec']
