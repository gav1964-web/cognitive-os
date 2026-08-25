"""Stable facade for split `config_doctor` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['config_doctor_part1', 'config_doctor_part2', 'config_doctor_part3', 'config_doctor_part4']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['run_config_doctor']
