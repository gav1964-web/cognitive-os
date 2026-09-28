"""Evaluate role maturity by project stratum and cross-cutting risk profile."""

from __future__ import annotations

from .role_project_type_cases import (
    _case_with_loaded_artifacts,
    _classification_debt,
    _foundation_case_is_current,
    _latest_foundation_reports,
    _project_development_evaluation_case,
    _resolved,
)
from .role_project_type_classification import (
    _active_side_effect_policy,
    _classification_evidence,
    _contract_family,
    _contract_family_override,
    _entrypoint_identity_override,
    _first_object,
    _first_value,
    _marker_matches,
    _matched_stratum,
    _normalized_text,
    _project_archetype,
    _project_report_risk_signals,
    _project_shape,
    _risk_evidence,
    classify_project_case,
)
from .role_project_type_evaluation_core import build_role_project_type_evaluation
from .role_project_type_evaluation_policy import (
    DEFAULT_POLICY_PATH,
    ROOT,
    RoleProjectTypeEvaluationError,
    load_role_project_type_policy,
)
from .role_project_type_markdown import render_role_project_type_markdown
from .role_project_type_scoring import (
    _cell,
    _development_target,
    _heatmap,
    _priority,
    _role_scores,
    _role_summary,
    _transformation_evidence_scope,
)

__all__ = [
    "DEFAULT_POLICY_PATH",
    "ROOT",
    "RoleProjectTypeEvaluationError",
    "build_role_project_type_evaluation",
    "classify_project_case",
    "load_role_project_type_policy",
    "render_role_project_type_markdown",
]
