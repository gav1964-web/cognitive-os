"""Stable facade for split `deterministic_goal_planner` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['deterministic_goal_planner_part1', 'deterministic_goal_planner_part2_1', 'deterministic_goal_planner_part3']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['plan_from_required_capabilities']
