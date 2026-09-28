"""Stable facade for split `project_facts` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['project_facts_part1', 'project_facts_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['facts_from_project_report', 'llm_fact_digest']
