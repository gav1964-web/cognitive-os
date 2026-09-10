"""Stable facade for split `llm_sandbox_implementation` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['llm_sandbox_implementation_part1', 'llm_sandbox_implementation_part2', 'llm_sandbox_implementation_part3', 'llm_sandbox_implementation_part4', 'llm_sandbox_implementation_part5', 'llm_sandbox_implementation_part6']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

_RUN_LLM_SANDBOX_IMPLEMENTATION = globals()["run_llm_sandbox_implementation"]

def _sync_part_globals() -> None:
    current = {key: value for key, value in globals().items() if not key.startswith("__")}
    for part in _PARTS:
        vars(part).update(current)

def run_llm_sandbox_implementation(*args, **kwargs):
    _sync_part_globals()
    return _RUN_LLM_SANDBOX_IMPLEMENTATION(*args, **kwargs)

__all__ = ['SandboxOperation', 'run_llm_sandbox_implementation']
