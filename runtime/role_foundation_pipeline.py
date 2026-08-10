"""Stable facade for split `role_foundation_pipeline` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = [
    'role_foundation_pipeline_part1',
    'role_foundation_pipeline_part2',
    'role_foundation_pipeline_part3',
    'role_foundation_pipeline_part4',
]
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['run_role_foundation_pipeline', 'run_role_foundation_benchmark', 'run_role_foundation_case', 'score_role_foundation', 'write_role_foundation_report']
