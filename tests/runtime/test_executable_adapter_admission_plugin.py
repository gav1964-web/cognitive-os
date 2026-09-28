import json

import pytest

from runtime.executable_acceptance_policy import dependency_stub_policy
from runtime.improvement_plugins import executable_adapter_admission as admission
from runtime.knowledge_admission import build_kb_candidate, write_kb_candidate
from runtime.promoted_executable_adapters import (
    load_executable_adapters,
    temporary_executable_adapters,
    validate_executable_adapter,
)
from runtime.self_improvement_analysis import _adapter_proposal_violations
from runtime.self_improvement_plugin_loader import enabled_improvement_plugins


def _root(tmp_path):
    path = tmp_path / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": "promoted_executable_adapters.v1", "adapters": []}),
        encoding="utf-8",
    )
    return tmp_path


def _proposal(module="optional_sdk"):
    return {
        "artifact_type": "ExecutableCapabilityAdapterProposal",
        "id": f"generated_module:{module}",
        "kind": "generated_module_profile",
        "module": module,
        "profile": {
            "attrs": {
                "Client": {"__fixture__": "stub_class"},
                "normalize": {"__fixture__": "callable_identity"},
            }
        },
    }


def _stage(root, project, *, status="confirmed", proposal=None):
    candidate = build_kb_candidate(
        record_type="foundation_capability_gap",
        proposed_record={
            "failure_class": "dependency_boundary",
            "gap_id": "dependency_boundary:no_viable_executable_candidate",
            "capability_adapter_proposal": proposal or _proposal(),
        },
        source_cases=[{"project": project, "status": status, "before": 8.8, "after": 8.8}],
        teacher_reference="measured dependency boundary",
    )
    write_kb_candidate(candidate, root=root)


def _evaluation(score, signal):
    return {
        "status": "ok",
        "project_min_score": score,
        "role_scores": {"project_analyzer": score, "architect": score, "spec_writer": score},
        "selected_extraction_candidate": "app.py:run",
        "downstream_evidence": {"acceptance_signal": signal},
    }


def test_adapter_trial_uses_temporary_profile_without_auto_promotion(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()

    def evaluate(*_args, **_kwargs):
        active = "optional_sdk" in dependency_stub_policy()["generated_module_profiles"]
        return _evaluation(9.7 if active else 8.8, "executable_callable" if active else "meta_only")

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)
    monkeypatch.setattr("runtime.self_improvement_training._source_fingerprint", lambda _path: "unchanged")
    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "diagnosis": {"failure_class": "dependency_boundary"},
        "promote": False,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "trial_passed"
    assert result["promotion_applied"] is False
    assert result["evolution"]["gates"]["raw_llm_code_executed"] is False
    assert load_executable_adapters(
        str(root / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json")
    )["adapters"] == []


def test_explicit_promotion_admits_adapter_after_holdout(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: {
        "status": "confirmed_adapter_effect",
        "score_delta": 0.9,
        "role_regressions": [],
        "source_project_unchanged": True,
        "same_selected_source": True,
        "control": _evaluation(8.8, "meta_only"),
        "treatment": _evaluation(9.7, "executable_callable"),
    })

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "diagnosis": {"failure_class": "dependency_boundary"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "promoted"
    catalog = load_executable_adapters(
        str(root / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json")
    )
    assert catalog["adapters"][0]["activation"] == "acceptance_sandbox_only"
    assert catalog["adapters"][0]["promotion_evidence"]["holdout_project"] == "holdout"


def test_adapter_requires_three_independent_confirmed_projects(tmp_path):
    root = _root(tmp_path)
    _stage(root, "alpha")
    _stage(root, "beta")
    _stage(root, "gamma", status="observed")
    holdout = root / "holdout"
    holdout.mkdir()

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "diagnosis": {"failure_class": "dependency_boundary"},
        "promote": False,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "confirmed_cases_required"
    assert result["maximum_confirmed_case_count"] == 2


def test_adapter_rejects_training_project_as_holdout(tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "alpha"
    holdout.mkdir()

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "diagnosis": {"failure_class": "dependency_boundary"},
        "promote": False,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "independent_holdout_required"


@pytest.mark.parametrize("unsafe", [
    {"Client": {"__fixture__": "run_shell"}},
    {"Client": {"source": "import os; os.system('whoami')"}},
])
def test_adapter_rejects_unknown_fixture_and_raw_code(unsafe):
    adapter = {
        "id": "generated_module:optional_sdk",
        "kind": "generated_module_profile",
        "module": "optional_sdk",
        "profile": {"attrs": unsafe},
        "activation": "acceptance_sandbox_only",
    }

    with pytest.raises(ValueError):
        validate_executable_adapter(adapter)


def test_diagnosis_rejects_unsafe_adapter_proposal():
    proposal = _proposal()
    proposal["profile"]["attrs"]["Client"] = {"code": "open('outside', 'w')"}

    assert _adapter_proposal_violations(proposal) == ["capability_adapter_proposal_invalid_or_unsafe"]
    assert _adapter_proposal_violations(_proposal()) == []


def test_diagnosis_rejects_hidden_code_beside_profile():
    proposal = _proposal()
    proposal["source"] = "import os"

    assert _adapter_proposal_violations(proposal) == ["capability_adapter_proposal_invalid_or_unsafe"]


def test_adapter_cannot_target_standard_library():
    proposal = _proposal("subprocess")

    assert admission._adapter_from_proposal(proposal) == {}


def test_training_catalog_never_auto_promotes_executable_adapter():
    plugins = {row["id"]: row for row in enabled_improvement_plugins()}

    assert plugins["executable_adapter_admission"]["auto_promote"] is False
    assert list(plugins).index("candidate_selection_admission") < list(plugins).index(
        "executable_adapter_admission"
    )


def test_temporary_adapter_is_visible_only_inside_acceptance_context():
    adapter = admission._adapter_from_proposal(_proposal("temporary_sdk"))

    assert "temporary_sdk" not in dependency_stub_policy()["generated_module_profiles"]
    with temporary_executable_adapters([adapter]):
        profile = dependency_stub_policy()["generated_module_profiles"]["temporary_sdk"]
        assert profile["attrs"]["normalize"]["__fixture__"] == "callable_identity"
    assert "temporary_sdk" not in dependency_stub_policy()["generated_module_profiles"]


def test_curated_config_profile_wins_over_learned_adapter():
    adapter = admission._adapter_from_proposal({
        **_proposal("borg._version"),
        "profile": {"attrs": {"version": "learned-value"}},
    })

    with temporary_executable_adapters([adapter]):
        profile = dependency_stub_policy()["generated_module_profiles"]["borg._version"]

    assert profile["attrs"]["version"] == "1.2.3"
