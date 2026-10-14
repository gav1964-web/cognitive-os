"""Stable facade for split `architecture_analysis_document` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['architecture_analysis_document_part1', 'architecture_analysis_document_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['write_architecture_analysis_document', 'render_architecture_analysis_document']
