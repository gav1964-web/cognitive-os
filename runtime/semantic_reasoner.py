"""Stable facade for split `semantic_reasoner` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['semantic_reasoner_part1', 'semantic_reasoner_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

_RUN_SEMANTIC_REASONER = globals()["run_semantic_reasoner"]

def _sync_part_globals() -> None:
    current = {key: value for key, value in globals().items() if not key.startswith("__")}
    for part in _PARTS:
        vars(part).update(current)

def run_semantic_reasoner(*args, **kwargs):
    _sync_part_globals()
    return _RUN_SEMANTIC_REASONER(*args, **kwargs)

__all__ = ['build_semantic_hypothesis_request', 'run_semantic_reasoner', 'build_stage2_template_backlog_item', 'validate_semantic_hypothesis_proposal']
