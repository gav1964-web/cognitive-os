from unittest.mock import patch

from runtime.local_inference import LocalInferenceConfig
from runtime.promoted_executable_adapters import validate_executable_adapter
from runtime.self_improvement_analysis import diagnose_training_failure
from runtime.self_improvement_evidence_proposals import (
    attach_evidence_proposal,
    build_evidence_proposal,
    load_proposal_recipes,
)


def _config(model):
    return LocalInferenceConfig(base_url="http://test", model=model, provider_label=model)


def _response():
    return {
        "failure_class": "dependency_management",
        "diagnosis": "An undeclared optional dependency blocks isolated import.",
        "hypothesis": "Use a bounded generated module profile in acceptance only.",
        "confidence": 0.95,
        "target_roles": ["architect", "spec_writer"],
        "parameter_changes": ["staged_kb_candidate"],
        "proposed_knowledge": {},
        "recommended_source": "",
    }


def _packet(reason="import_failed_missing_module", detail="ModuleNotFoundError: No module named 'optional_sdk.transport'"):
    return {
        "downstream_evidence": {
            "acceptance_signal": "meta_only",
            "summary": {
                "skipped_reason_counts": {reason: 1},
                "skipped_targets": [{
                    "reason": reason,
                    "detail": detail,
                    "target": "app.py:run",
                }],
            },
        }
    }


def test_missing_module_evidence_builds_sandbox_adapter_without_teacher():
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=_response()) as mocked:
        result = diagnose_training_failure(
            _packet(),
            local_config=_config("local"),
            teacher_config=_config("teacher"),
        )

    assert mocked.call_count == 1
    assert result["status"] == "ok"
    assert result["failure_class"] == "dependency_boundary"
    proposal = result["proposed_knowledge"]["capability_adapter_proposal"]
    assert proposal["module"] == "optional_sdk.transport"
    assert proposal["profile"]["attrs"]["__getattr__"] == {"__fixture__": "module_getattr_stub"}
    assert result["proposal_provenance"] == [{
        "proposal": "capability_adapter_proposal",
        "source": "executable_acceptance_evidence",
        "recipe_id": "missing_module_getattr_adapter",
        "reason": "import_failed_missing_module",
    }]


def test_runtime_import_error_does_not_masquerade_as_missing_module():
    result = build_evidence_proposal(_packet(
        reason="import_failed_runtime_error",
        detail="function '_has_torch_function' already has a docstring",
    ))

    assert result == {}


def test_malformed_or_standard_library_module_is_rejected():
    assert build_evidence_proposal(_packet(detail="No module named optional_sdk")) == {}
    assert build_evidence_proposal(_packet(detail="No module named 'subprocess'")) == {}


def test_evidence_proposal_supersedes_conflicting_llm_adapter():
    diagnosis = {
        "proposed_knowledge": {"capability_adapter_proposal": {"module": "invented_sdk"}},
        "proposal_rejections": [],
    }

    result = attach_evidence_proposal(_packet(), diagnosis)

    proposal = result["proposed_knowledge"]["capability_adapter_proposal"]
    assert proposal["module"] == "optional_sdk.transport"
    assert result["proposal_rejections"] == [{
        "proposal": "capability_adapter_proposal",
        "violations": ["superseded_by_executable_acceptance_evidence"],
    }]


def test_only_exact_module_getattr_dunder_is_allowed():
    valid = {
        "id": "generated_module:optional_sdk",
        "kind": "generated_module_profile",
        "module": "optional_sdk",
        "profile": {"attrs": {"__getattr__": {"__fixture__": "module_getattr_stub"}}},
        "activation": "acceptance_sandbox_only",
    }

    assert validate_executable_adapter(valid) == valid
    invalid = {**valid, "profile": {"attrs": {"__getattr__": {"__fixture__": "callable_noop"}}}}
    try:
        validate_executable_adapter(invalid)
    except ValueError as exc:
        assert "invalid executable adapter attribute" in str(exc)
    else:
        raise AssertionError("unsafe dunder fixture was accepted")


def test_proposal_recipe_catalog_is_validated():
    catalog = load_proposal_recipes()

    assert catalog["recipes"][0]["activation"] == "acceptance_sandbox_only"
