"""Stable facade for split executor profile-safe role probe implementation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_PART_NAMES = [
    "executor_profile_safe_role_probe_part1",
    "executor_profile_safe_role_probe_part2",
    "executor_profile_safe_role_probe_part3",
    "executor_profile_safe_role_probe_part4",
    "executor_profile_safe_role_probe_part5",
    "executor_profile_safe_role_probe_part6",
    "executor_profile_safe_role_probe_part7",
    "executor_profile_safe_role_probe_part8",
]
_PARTS = [importlib.import_module(f"tools._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ["run_profile_safe_role_probe", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
