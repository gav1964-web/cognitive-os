"""Stable facade for split `role_artifact_quality` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['role_artifact_quality_part1', 'role_artifact_quality_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

__all__ = ['evaluate_role_artifacts', 'evaluate_project_map_report', 'evaluate_architecture_decision', 'evaluate_technical_spec', 'evaluate_implementation_plan', 'evaluate_test_plan', 'evaluate_review_findings']
