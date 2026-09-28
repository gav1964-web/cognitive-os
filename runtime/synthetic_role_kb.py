"""Stable facade for split `synthetic_role_kb` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['synthetic_role_kb_part1', 'synthetic_role_kb_part2', 'synthetic_role_kb_part3']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

_GENERATE_LLM_ROLE_QA = globals()["generate_llm_role_qa"]

def _sync_part_globals() -> None:
    current = {key: value for key, value in globals().items() if not key.startswith("__")}
    for part in _PARTS:
        vars(part).update(current)

def generate_llm_role_qa(*args, **kwargs):
    _sync_part_globals()
    return _GENERATE_LLM_ROLE_QA(*args, **kwargs)

__all__ = ['SyntheticRoleKbError', 'SyntheticRoleQaRecord', 'load_synthetic_policy', 'generate_synthetic_role_qa', 'write_synthetic_role_qa', 'write_llm_role_qa', 'generate_llm_role_qa', 'load_synthetic_role_qa', 'role_qa_records_from_kb', 'synthetic_role_qa_summary', 'search_synthetic_role_qa', 'record_role_qa_feedback', 'synthetic_probe_report', 'synthetic_role_qa_audit']
