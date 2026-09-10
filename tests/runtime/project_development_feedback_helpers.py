from __future__ import annotations

from pathlib import Path
from copy import deepcopy

from runtime.contract_registry import ContractRegistry
from runtime.project_development import load_project_development_policy
from runtime.project_development_bounded_experiment import admit_bounded_experiment_proposal
from runtime.project_development_bounded_evidence import (
    collect_bounded_experiment_evidence,
    decide_bounded_experiment_evidence,
)
from runtime.project_development_implementation_design import admit_implementation_design
from runtime.project_development_feedback import run_project_development_feedback_continuation


def _feedback(target: str, *, reason: str = "no_unique_development_helper_extraction") -> dict:
    return {
        "artifact_type": "ProjectDevelopmentExecutionFeedback",
        "status": "action_required",
        "decision": "research",
        "reason": reason,
        "next_roles": ["researcher", "architect"],
        "evidence": {
            "selected_target": target,
            "reducer_attempts": [{
                "operation_kind": "extract_append_mapping_helper",
                "status": "skipped",
                "reason": "append_mapping_helper_pattern_not_proven",
            }],
        },
        "constraints": {
            "automatic_retry": False,
            "allowed_targets_preserved": True,
            "scope_expansion_allowed": False,
            "source_apply_allowed": False,
        },
    }


def _baselines(target: str) -> tuple[dict, dict]:
    policy = load_project_development_policy()
    decision = {
        "artifact_type": "ProjectDevelopmentDecision",
        "status": "selected",
        "selected_issue": {
            "issue_id": "ISSUE-001",
            "rule_id": "mixed_responsibility",
            "evidence": [target],
            "affected_targets": [target],
        },
        "selected_option": {
            "option_id": "ISSUE-001:bounded_decomposition",
            "issue_id": "ISSUE-001",
            "route": "role_chain",
            "evidence": [target],
        },
    }
    outcome = {
        "artifact_type": "ProjectDevelopmentOutcomeContract",
        "status": "defined",
        "baseline_evidence": [target],
        "required_checks": list(policy["outcome_policy"]["required_checks"]),
        "reassessment": "rerun diagnosis",
    }
    return decision, outcome













__all__ = [name for name in globals() if not name.startswith("__")]
