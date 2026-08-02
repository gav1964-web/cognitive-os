"""Stable facade for split `goal_intake` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['goal_intake_part1', 'goal_intake_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['ClarificationPacket', 'GoalSpec', 'build_goal_spec', 'validate_goal_spec', 'merge_clarification']
