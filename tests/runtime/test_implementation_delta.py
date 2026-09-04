from pathlib import Path

from runtime.implementation_delta import build_implementation_delta
from runtime.implementation_plan_builder import build_implementation_plan
from runtime.programmer_patch_synthesizer import synthesize_patch_package


def _contract(snippet: str = "return value.strip()") -> dict:
    return {
        "candidate": "pkg/core.py:normalize",
        "ranked_candidates": [
            {"source": "pkg/core.py:normalize", "snippet": snippet},
        ],
    }


def test_discovery_goal_emits_verification_only_delta() -> None:
    delta = build_implementation_delta(
        {"goal": "Assess and prepare first safe transformation for demo"},
        _contract(),
        [{"id": "AC-001"}],
    )

    assert delta["status"] == "verification_only"
    assert delta["intent"]["kind"] == "verify_existing_contract"
    assert delta["acceptance_ids"] == ["AC-001"]


def test_explicit_change_requires_semantic_synthesis() -> None:
    delta = build_implementation_delta(
        {"goal": "Remove automatic fallback from normalize"},
        _contract(),
        [{"id": "AC-001"}],
    )

    assert delta["status"] == "semantic_synthesis_required"
    assert delta["intent"] == {
        "kind": "user_requested_change",
        "statement": "Remove automatic fallback from normalize",
    }


def test_explicit_change_with_verified_profile_is_ready() -> None:
    contract = _contract()
    contract["contract_profile"] = {
        "id": "normalize_string",
        "operator_id": "strip_lower",
        "source": "contract_transform_contract_profiles",
    }
    delta = build_implementation_delta(
        {"goal": "Implement deterministic normalization"}, contract, [{"id": "AC-001"}]
    )

    assert delta["status"] == "ready"
    assert delta["intent"]["operator_id"] == "strip_lower"


def test_source_backed_stub_requires_failure_evidence_before_synthesis() -> None:
    delta = build_implementation_delta(
        {"goal": "Assess module"},
        _contract("def normalize(value):\n    raise NotImplementedError"),
        [],
    )

    assert delta["status"] == "verification_only"
    assert delta["intent"]["kind"] == "characterize_incomplete_candidate"
    assert "observation only" in delta["reason"]


def test_implementer_propagates_verification_only_delta() -> None:
    delta = build_implementation_delta({"goal": "Assess project"}, _contract(), [])
    plan = build_implementation_plan(
        technical_spec={
            "artifact_type": "TechnicalSpec",
            "requirements": [],
            "acceptance_criteria": [{"id": "AC-001", "source": "pkg/core.py:normalize"}],
            "implementation_handoff": {"patch_scope": ["pkg/core.py:normalize"]},
            "extraction_contract": _contract(),
            "implementation_delta": delta,
            "source_evidence": [{"source": "pkg/core.py:normalize"}],
        }
    )

    assert plan["implementation_delta"]["status"] == "verification_only"
    assert plan["patch_intent"]["status"] == "verification_only"
    assert plan["implementation_blueprint"]["operation"] == "verify_existing_contract"


def test_patch_synthesis_does_not_invent_verification_only_patch(tmp_path: Path) -> None:
    synthesis = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=tmp_path / "project",
        implementation_plan={"implementation_delta": {"status": "verification_only"}},
        test_plan={},
    )

    assert synthesis["status"] == "verification_only"
    assert synthesis["patches"] == []
    assert not (tmp_path / "execution" / "patch_sandbox").exists()


def test_semantic_delta_waits_for_l45_patch_hypothesis(tmp_path: Path) -> None:
    synthesis = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=tmp_path / "project",
        implementation_plan={"implementation_delta": {"status": "semantic_synthesis_required"}},
        test_plan={},
    )

    assert synthesis["status"] == "skipped"
    assert synthesis["reason"] == "semantic_delta_requires_patch_hypothesis"
    assert not (tmp_path / "execution" / "patch_sandbox").exists()
