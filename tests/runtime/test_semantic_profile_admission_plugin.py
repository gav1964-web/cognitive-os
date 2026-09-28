import json

from runtime.improvement_plugins import semantic_profile_admission as admission
from runtime.knowledge_admission import build_kb_candidate, grouped_candidate_report, write_kb_candidate
from runtime.promoted_semantic_contract_profiles import (
    load_promoted_profiles,
    promote_profile,
    promoted_contract_for_candidate,
)
from runtime.target_quality import semantic_target_quality_report


PROFILE = {
    "id": "external_api_command_boundary",
    "contract_family": "external_api_command_boundary",
    "input_contract": {"command": "Command"},
    "output_contract": {"result": "Result"},
    "side_effect_policy": {"declared": ["network"]},
    "validation_gates": ["transport is isolated"],
    "failure_modes": ["transport_failure"],
    "recognition_policy": {
        "source": "python_ast",
        "recognizer": "external_api_command_boundary",
        "required_evidence": [
            "bounded_body", "command_inputs", "delegated_result", "instance_transport",
            "payload_projection", "public_command", "write_transport",
        ],
    },
    "benign_runtime_boundary": True,
    "numeric_bonus_from_training": False,
}


def _recognized_profile():
    return {
        **PROFILE,
        "training_evidence": {
            key: True for key in PROFILE["recognition_policy"]["required_evidence"]
        },
    }


def _root(tmp_path):
    path = tmp_path / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": "promoted_semantic_contract_profiles.v1", "profiles": []}),
        encoding="utf-8",
    )
    return tmp_path


def _stage(root, project):
    candidate = build_kb_candidate(
        record_type="semantic_contract_profile_template",
        proposed_record=PROFILE,
        source_cases=[{"project": project, "status": "confirmed", "before": 8.8, "after": 9.7}],
        teacher_reference="measured profile effect",
    )
    write_kb_candidate(candidate, root=root)


def _project(root, name="holdout"):
    project = root / name
    project.mkdir()
    (project / "client.py").write_text(
        "class Client:\n"
        "    def publish(self, target, payload):\n"
        "        return self._post(target, data={'payload': payload})\n",
        encoding="utf-8",
    )
    return project


def _effect(source):
    return {
        "status": "confirmed_profile_effect",
        "source": source,
        "contract_family": "external_api_command_boundary",
        "score_delta": 0.9,
        "role_regressions": [],
        "control": {"status": "ok", "project_min_score": 8.8, "role_scores": {"spec_writer": 8.8}},
        "treatment": {"status": "ok", "project_min_score": 9.7, "role_scores": {"spec_writer": 9.7}},
    }


def test_promoted_profile_matches_new_symbol_by_ast(tmp_path):
    root = _root(tmp_path)
    promote_profile(root=root, profile=PROFILE, promotion_evidence={"holdout": "independent"})

    result = promoted_contract_for_candidate(
        {"snippet": "def revoke(self, token=None):\n    return self._delete('token', params={'token': token})\n"},
        path=str(root / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json"),
    )

    assert result["contract_family"] == "external_api_command_boundary"
    assert result["knowledge_profile"] == "promoted:external_api_command_boundary"


def test_admission_promotes_after_three_cases_and_holdout(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = _project(root)
    monkeypatch.setattr(admission, "synthesize_contract_profile", lambda *_args: _recognized_profile())
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: _effect("client.py:publish"))

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {"selected_candidate": "client.py:publish"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "promoted"
    assert result["evolution"]["gates"] == {
        "repeated_confirmed_cases": True,
        "independent_holdout": True,
        "same_source_effect": True,
        "no_role_regression": True,
    }
    catalog = load_promoted_profiles(
        str(root / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json")
    )
    assert [row["id"] for row in catalog["profiles"]] == ["external_api_command_boundary"]


def test_admission_waits_for_enough_independent_cases(monkeypatch, tmp_path):
    root = _root(tmp_path)
    _stage(root, "alpha")
    _stage(root, "beta")
    holdout = _project(root)
    monkeypatch.setattr(admission, "synthesize_contract_profile", lambda *_args: _recognized_profile())

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {"selected_candidate": "client.py:publish"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["confirmed_case_count"] == 2


def test_grouped_semantic_profiles_use_family_id():
    candidate = build_kb_candidate(
        record_type="semantic_contract_profile_template",
        proposed_record=PROFILE,
        source_cases=[{"project": "alpha", "status": "confirmed"}],
        teacher_reference="trial",
    )

    report = grouped_candidate_report([candidate])

    assert report["groups"][0]["proposed_id"] == "external_api_command_boundary"
    assert report["groups"][0]["group_key"].endswith(":external_api_command_boundary")


def test_quality_accepts_promoted_profile_without_numeric_bonus():
    result = semantic_target_quality_report(
        "client.py:publish",
        structural_evidence={"argument_count": 2, "return_paths": 1},
        recognized_profile=PROFILE,
    )

    assert result["profiled_contract_family"] is True
    assert "external_api_command_boundary" in result["semantic_profile_ids"]
