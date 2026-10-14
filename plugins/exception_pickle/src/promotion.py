"""Pure promotion-document preparation; authorization and writes stay outside."""
from __future__ import annotations

from typing import Any


def prepare_promotion_catalog(
    *, readiness: dict[str, Any], evaluator: dict[str, Any], holdout: dict[str, Any], generated_at: str
) -> dict[str, Any]:
    evidence = dict(readiness.get("evidence") or {})
    return {
        "schema_version": "exception_pickle_reconstruction_patterns.v1",
        "status": "active",
        "activated_at": generated_at,
        "promotion_authority": "explicit_exception_pickle_promotion_transaction",
        "operator": {
            "id": "preserve_exception_constructor_reconstruction",
            "status": "validated_active",
            "hypothesis_kind": "exception_pickle_reconstruction_boundary",
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
            "applicability": {
                "required_constructor_inputs_must_be_stored_on_self": True,
                "maximum_required_constructor_inputs": 4,
                "existing_reconstruction_hook_blocks": True,
                "single_class_constructor_target": True,
                "generated_function_stubs_forbidden": True,
            },
        },
        "promotion_evidence": {
            "supervised_reports": list(evidence.get("reports") or []),
            "autonomous_reports": list(evidence.get("autonomous_reports") or []),
            "independent_evaluator": dict(evaluator.get("evidence") or {}),
            "holdout_candidate_count": holdout.get("holdout_candidate_count"),
            "holdout_project_count": holdout.get("holdout_project_count"),
        },
        "safety": {
            "source_apply_allowed": False,
            "automatic_runtime_mutation_allowed": False,
            "requires_sandbox_patch": True,
            "requires_semantic_replay": True,
        },
    }

