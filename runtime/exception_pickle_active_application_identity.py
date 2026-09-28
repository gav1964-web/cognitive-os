"""Candidate identity helpers for active exception-pickle application."""

from __future__ import annotations

from typing import Any

def _candidate_project(row: dict[str, Any]) -> str:
    return str(row.get("canonical_project") or row.get("project") or "")


def _candidate_target(row: dict[str, Any]) -> str:
    return f"{row.get('path')}:{row.get('class_name')}.__init__"


def _candidate_key(row: dict[str, Any]) -> str:
    return f"{_candidate_project(row)}::{_candidate_target(row)}"


def _candidate_readmission_subtype(row: dict[str, Any]) -> str:
    if bool(row.get("formatted_super_argument")):
        return "derived_message_sample"
    required = [str(value).lower() for value in row.get("required_constructor_parameters") or []]
    if any(name in {"content", "auth_message", "spec", "dependents", "exceptions", "scored_successfully"} for name in required):
        return "method_object_sample"
    if any(name in {"response", "request", "record", "driver_error", "connection_key"} for name in required):
        return "source_backed_object_sample"
    return "direct_self_assignment_sample"
