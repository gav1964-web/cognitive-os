"""Stable facade for split GitHub full-chain probe implementation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from tools.split_facade_loader import load_split_namespace

_PART_NAMES = [
    "github_full_chain_probe_part1",
    "github_full_chain_probe_part2",
    "github_full_chain_probe_part3",
    "github_full_chain_probe_part4",
    "github_full_chain_probe_part5",
]
_PARTS, _MERGED, _SPLIT_COLLISIONS = load_split_namespace("tools._parts", _PART_NAMES)
globals().update(_MERGED)

__all__ = ["run_probe", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
