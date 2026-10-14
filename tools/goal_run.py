"""Stable facade for split `goal_run` implementation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_PART_NAMES = ['goal_run_part1', 'goal_run_part2']
_PARTS = [importlib.import_module(f"tools._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['main']

if __name__ == "__main__":
    raise SystemExit(main())
