"""Read-only source evidence helpers for project-development planning."""

from __future__ import annotations

from .project_development_source_incompleteness import (
    _FAILURE_AUTHORITIES,
    _body_is_stub,
    _comment_tokens,
    _decorator_name,
    _exception_suppression_findings,
    _failure_index,
    _is_nonproduction_source,
    _is_not_implemented,
    _nearby_comment_lines,
    _nearby_intent_comment,
    _parent_class,
    _stub_classification,
    _stub_findings,
    _stub_kind,
    collect_source_incompleteness_evidence,
)
from .project_development_source_targets import (
    _base_name,
    _loop_depth,
    _module_scope_statements,
    _target_function,
    _target_owner_class,
    collect_python_target_facts,
    resolve_python_target,
    target_source_digest,
)

__all__ = [
    "collect_python_target_facts",
    "collect_source_incompleteness_evidence",
    "resolve_python_target",
    "target_source_digest",
]
