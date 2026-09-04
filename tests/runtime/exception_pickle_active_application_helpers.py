import json
import subprocess
import sys
from pathlib import Path

from runtime.exception_pickle_active_application import (
    _candidate_effective_replay_risk,
    _candidate_has_self_reference_args_readmission_delta,
    _candidate_static_patch_risk,
    run_exception_pickle_active_application_trial,
)
from runtime.programmer_exception_pickle_patch import exception_pickle_reconstruction_patch


def _active_catalog() -> dict:
    return {
        "operator": {
            "id": "preserve_exception_constructor_reconstruction",
            "status": "validated_active",
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
            "applicability": {
                "maximum_required_constructor_inputs": 4,
            },
        },
    }


def _write_active_catalog(root: Path) -> None:
    path = root / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "schema_version": "exception_pickle_reconstruction_patterns.v1",
            "status": "active",
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
            "safety": {
                "source_apply_allowed": False,
                "automatic_runtime_mutation_allowed": False,
                "requires_sandbox_patch": True,
                "requires_semantic_replay": True,
            },
            "promotion_evidence": {
                "supervised_reports": [{}, {}, {}],
                "autonomous_reports": [{}],
                "holdout_project_count": 25,
            },
        }),
        encoding="utf-8",
    )


def _write_transfer_ledger(root: Path) -> Path:
    path = root / "ledger.json"
    path.write_text(
        json.dumps({
            "artifact_type": "SupervisedTransferLedger",
            "verified_count": 3,
            "autonomous_verified_count": 1,
            "cases": [{"project": "used"}],
            "autonomous_cases": [{"project": "auto-used"}],
        }),
        encoding="utf-8",
    )
    return path


__all__ = [name for name in globals() if not name.startswith("__")]
