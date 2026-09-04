"""Stable facade for split GitHub full-chain probe implementation."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

_PART_NAMES = [
    "github_full_chain_probe_part1",
    "github_full_chain_probe_part2",
    "github_full_chain_probe_part3",
    "github_full_chain_probe_part4",
    "github_full_chain_probe_part5",
]
_PARTS = [importlib.import_module(f"tools._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ["run_probe", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
