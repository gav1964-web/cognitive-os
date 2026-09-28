"""Stable facade for split executor profile-safe role probe implementation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.split_facade_loader import load_split_namespace

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
_PARTS, _MERGED, _SPLIT_COLLISIONS = load_split_namespace("tools._parts", _PART_NAMES)
globals().update(_MERGED)

__all__ = ["run_profile_safe_role_probe", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
