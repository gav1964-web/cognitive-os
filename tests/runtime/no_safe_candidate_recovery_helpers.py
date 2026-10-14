from pathlib import Path
import shutil

from runtime.no_safe_candidate_recovery import run_no_safe_candidate_recovery
from runtime.contract_registry import ContractRegistry
from runtime.role_pipeline import run_role_pipeline
from runtime.programmer_patch_synthesizer import synthesize_recovery_patch_package
from runtime.recovery_patch_verification import verify_recovery_patch_package
from runtime.recovery_patch_admission import (
    apply_recovery_patch,
    build_recovery_patch_admission,
    rollback_recovery_patch,
)
from runtime.recovery_patch_session import run_recovery_patch_session




































def _blocked_spec(target: str = "legacy.py:process_all") -> dict:
    return {
        "first_slice_reselection_request": {
            "trigger": "no_semantically_safe_candidate_in_approved_first_slice",
            "resolution_status": "exhausted",
            "terminal": True,
            "outcome": {
                "candidate_viability": [{
                    "target": target,
                    "semantic_score": 70,
                    "status": "deferred",
                    "observed_side_effects": ["filesystem", "filesystem_read", "subprocess"],
                    "matched_rules": [{"rule_id": "external_effect_boundary"}],
                }]
            },
        }
    }


def _escalated_control() -> dict:
    return {
        "semantic_escalation": {
            "l4_5_required": True,
            "reasons": ["no_safe_source_specific_candidate"],
        }
    }

__all__ = [name for name in globals() if not name.startswith("__")]
