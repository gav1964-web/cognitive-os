from __future__ import annotations

from pathlib import Path

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError
from runtime.project_development_llm_hypothesis import (
    build_llm_failure_hypothesis,
    enrich_with_llm_failure_hypothesis,
)
from runtime.project_development import run_project_development


def _config() -> LocalInferenceConfig:
    return LocalInferenceConfig(base_url="http://example.test/v1", model="test")


def _issue() -> dict:
    return {
        "issue_id": "ISSUE-1",
        "failure_specific_reducer_required": True,
        "affected_targets": ["module.py:parse_value"],
        "failure_evidence": [{
            "target": "module.py:parse_value",
            "authority": "failing_contract_test",
            "failure_signature": "failure-digest",
            "detail": "ValueError is raised for an empty optional value",
            "failing_nodeids": ["tests/test_module.py::test_empty_value"],
        }],
        "allowed_operator_ids": [],
    }


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "def parse_value(value: str) -> str:\n"
        "    return value.split(':', 1)[1]\n",
        encoding="utf-8",
    )
    return project


def _payload() -> dict:
    return {
        "target": "module.py:parse_value",
        "failure_signature": "failure-digest",
        "mechanism": "The parser indexes a missing delimiter field before recognizing optional empty input.",
        "repair_mechanism": "Recognize the empty optional form before delimiter-dependent extraction.",
        "mutation_contract": {
            "precondition": "The input is empty and the contract permits absence.",
            "change": "Return the declared empty representation before splitting.",
            "preserved_behavior": "Delimited non-empty values retain their current parsed result.",
        },
        "residual_risks": ["Malformed non-empty values must continue to fail explicitly."],
        "confidence": 0.76,
    }


def test_llm_hypothesis_is_evidence_bound_but_never_authorized(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: _payload(),
    )

    result = enrich_with_llm_failure_hypothesis(
        {"issues": [_issue()]}, project_dir=_project(tmp_path), config=_config()
    )
    issue = result["issues"][0]

    assert issue["llm_hypothesis_advisory"]["status"] == "accepted_hypothesis_only"
    assert issue["causal_hypothesis"]["execution_authority"] is False
    assert issue["repair_design"]["source_apply"] is False
    assert issue["proposed_operator_ids"] == []
    assert issue["allowed_operator_ids"] == []


def test_llm_hypothesis_rejects_target_drift_and_patch_fields(tmp_path, monkeypatch) -> None:
    payload = _payload()
    payload["target"] = "module.py:other"
    payload["patch"] = "untrusted patch"
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: payload,
    )

    advisory = build_llm_failure_hypothesis(
        issue=_issue(), project_dir=_project(tmp_path), config=_config()
    )

    assert advisory["status"] == "rejected"
    assert "target_mismatch" in advisory["errors"]
    assert "forbidden_fields:patch" in advisory["errors"]


def test_llm_hypothesis_rejects_low_confidence_and_unknown_schema(tmp_path, monkeypatch) -> None:
    payload = _payload()
    payload["confidence"] = 0.4
    payload["surprise"] = "uncontracted field"
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: payload,
    )

    advisory = build_llm_failure_hypothesis(
        issue=_issue(), project_dir=_project(tmp_path), config=_config()
    )

    assert advisory["status"] == "rejected"
    assert "confidence_below_threshold" in advisory["errors"]
    assert "unknown_fields:surprise" in advisory["errors"]


def test_llm_hypothesis_rejects_malformed_contract_types(tmp_path, monkeypatch) -> None:
    payload = _payload()
    payload["mutation_contract"] = ["not", "an", "object"]
    payload["residual_risks"] = "not-a-list"
    payload["confidence"] = True
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: payload,
    )

    advisory = build_llm_failure_hypothesis(
        issue=_issue(), project_dir=_project(tmp_path), config=_config()
    )

    assert advisory["status"] == "rejected"
    assert "mutation_contract_object_required" in advisory["errors"]
    assert "residual_risks_required" in advisory["errors"]
    assert "confidence_out_of_range" in advisory["errors"]


def test_llm_hypothesis_rejects_non_object_provider_response(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: ["not", "an", "object"],
    )

    advisory = build_llm_failure_hypothesis(
        issue=_issue(), project_dir=_project(tmp_path), config=_config()
    )

    assert advisory["status"] == "rejected"
    assert advisory["errors"] == ["response_object_required"]


def test_llm_hypothesis_cannot_read_target_outside_project(tmp_path, monkeypatch) -> None:
    project = _project(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("def parse_value(value):\n    return value\n", encoding="utf-8")
    issue = _issue()
    escaped_target = "../outside.py:parse_value"
    issue["affected_targets"] = [escaped_target]
    issue["failure_evidence"][0]["target"] = escaped_target
    called = False

    def fake_chat(messages, config=None):
        nonlocal called
        called = True
        return _payload()

    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat", fake_chat
    )
    advisory = build_llm_failure_hypothesis(
        issue=issue, project_dir=project, config=_config()
    )

    assert advisory["status"] == "rejected"
    assert advisory["errors"] == ["single_source_backed_failure_required"]
    assert called is False


def test_llm_hypothesis_failure_remains_a_controlled_advisory(tmp_path, monkeypatch) -> None:
    def unavailable(messages, config=None):
        raise LocalInferenceError("provider unavailable")

    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat", unavailable
    )
    original = {"issues": [_issue()]}
    result = enrich_with_llm_failure_hypothesis(
        original, project_dir=_project(tmp_path), config=_config()
    )

    assert result["issues"][0]["llm_hypothesis_advisory"]["status"] == "unavailable"
    assert "causal_hypothesis" not in result["issues"][0]
    assert original["issues"][0]["allowed_operator_ids"] == []


def test_llm_hypothesis_is_not_called_without_explicit_config(tmp_path, monkeypatch) -> None:
    called = False

    def fake_chat(messages, config=None):
        nonlocal called
        called = True
        return _payload()

    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat", fake_chat
    )
    original = {"issues": [_issue()]}

    assert enrich_with_llm_failure_hypothesis(
        original, project_dir=_project(tmp_path), config=None
    ) == original
    assert called is False


def test_project_development_reports_advisory_without_execution(tmp_path, monkeypatch) -> None:
    project = _project(tmp_path)
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'bounded-demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "runtime.project_development_llm_hypothesis.call_json_chat",
        lambda messages, config=None: _payload(),
    )

    result = run_project_development(
        root=Path(__file__).resolve().parents[2],
        project_dir=project,
        goal="Diagnose the evidence-backed parser failure",
        chain_case={
            "project_stratum": "library_pure_transform",
            "contract_failure_evidence": _issue()["failure_evidence"],
        },
        llm_hypothesis_config=_config(),
        run_role_chain=True,
    )
    issue = result["decision"]["selected_issue"]

    assert result["llm_hypothesis_summary"]["accepted_count"] == 1
    assert result["llm_hypothesis_summary"]["execution_authorized"] is False
    assert issue["allowed_operator_ids"] == []
    assert result["role_chain_handoff"]["status"] == "completed_aligned"
    assert result["role_chain_handoff"]["problem_outcome_conformance"]["status"] == "passed"
    synthesis = result["role_artifacts"]["architecture_decision"][
        "architecture_synthesis"
    ]
    assert synthesis["repair_design"]["status"] == "llm_hypothesis_review_required"
    assert result["safety"]["source_changes"] is False
