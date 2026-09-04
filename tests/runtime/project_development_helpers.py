from __future__ import annotations

from runtime.project_development import (
    build_development_diagnosis,
    build_development_options,
    build_outcome_contract,
    load_project_development_policy,
    select_development_option,
    _target_issue_aligned,
    _focused_project_report,
    _memory_context,
)
from runtime.project_development_experiment import (
    _admission,
    _experiment_artifact,
    _patch_scope_aligned,
    _reassessment,
    _validated_memory,
    build_project_development_execution_feedback,
)
from runtime.contract_registry import ContractRegistry
from runtime.project_development_delta import development_delta_transform


def _report() -> dict:
    return {
        "source_health": {"status": "clean", "project_shape": "single_project"},
        "risks": [{"code": "secret_material_in_source", "severity": "high", "detail": "src/settings.py"}],
        "answers": {
            "4_contracts_data": {
                "weak_contract_zones": ["pkg/service.py:run"],
                "actionable_contract_failures": [{
                    "target": "pkg/service.py:run",
                    "authority": "failing_contract_test",
                    "detail": "missing input fails outside the declared contract",
                }],
            },
            "6_runtime_extraction_readiness": {"mixed_responsibility_functions": []},
        },
    }

























































__all__ = [name for name in globals() if not name.startswith("__")]
