from __future__ import annotations

from tests.runtime.first_slice_reselection_request_helpers import *

def test_architect_qualifies_ambiguous_methods_during_reselection(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "adapter.py").write_text(
        "class JsonAdapter:\n    def transform(self, value):\n        return {'value': value}\n\n"
        "class CsvAdapter:\n    def transform(self, value):\n        return [value]\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    project_report["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "pkg/adapter.py", "name": "transform"}
    ]
    adr = _architecture_decision(tmp_path, project_report)
    spec = build_technical_spec(architecture_decision=adr)
    spec["first_slice_reselection_request"] = {
        "status": "required",
        "trigger": "ambiguous_method_symbol",
    }

    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=spec,
        project_report=project_report,
        iteration=1,
    )

    assert resolution["status"] == "selected"
    assert resolution["outcome"]["selected_targets"] == [
        "pkg/adapter.py:CsvAdapter.transform",
        "pkg/adapter.py:JsonAdapter.transform",
    ]


def test_configured_pipeline_rebuilds_spec_once_after_architect_reselection(monkeypatch):
    initial = {
        "architecture_decision": {"artifact_type": "ArchitectureDecisionRecord", "role": "architect"},
        "technical_spec": {
            "artifact_type": "TechnicalSpec",
            "role": "spec_writer",
            "first_slice_reselection_request": {"status": "required"},
        },
        "implementation_plan": {
            "artifact_type": "ImplementationPlan",
            "first_slice_reselection_request": {"status": "required"},
        },
    }
    revised = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "first_slice_reselection_history": [{"status": "selected"}],
    }
    calls = []

    monkeypatch.setattr(
        architect_reselection,
        "reselect_architecture_first_slice",
        lambda **kwargs: {"status": "selected", "architecture_decision": revised, "outcome": {"status": "selected"}},
    )

    def rerun(**kwargs):
        calls.append(kwargs)
        transform = kwargs["artifact_transform"]
        return {
            "architecture_decision": transform(
                {"artifact_type": "ArchitectureDecisionRecord", "role": "architect", "fresh": True}
            ),
            "technical_spec": transform(
                {
                    "artifact_type": "TechnicalSpec",
                    "role": "spec_writer",
                    "first_slice_reselection_request": {"status": "not_required"},
                }
            ),
            "implementation_plan": {
                "artifact_type": "ImplementationPlan",
                "first_slice_reselection_request": {"status": "not_required"},
            },
        }

    monkeypatch.setattr(configured_pipeline, "run_role_artifact_pipeline", rerun)
    result = configured_pipeline._close_first_slice_reselection_loop(
        artifacts=initial,
        goal="Select a ready slice",
        project_report={},
        pipeline={"steps": []},
        pipeline_kwargs={},
    )

    assert len(calls) == 1
    assert result["architecture_decision"] == revised
    request = result["technical_spec"]["first_slice_reselection_request"]
    assert request["status"] == "not_required"
    assert request["resolution_status"] == "selected"
    assert request["terminal"] is False
    assert result["implementation_plan"]["first_slice_reselection_request"] == request


def test_reselection_applies_user_transform_to_revised_architecture_decision():
    revised = {"artifact_type": "ArchitectureDecisionRecord", "reselected": True}

    def clamp(artifact):
        return {**artifact, "evaluation_target_clamp": {"target": "pkg/state.py:update"}}

    transform = configured_pipeline._replacement_transform(revised, clamp)
    result = transform({"artifact_type": "ArchitectureDecisionRecord", "original": True})

    assert result == {
        "artifact_type": "ArchitectureDecisionRecord",
        "reselected": True,
        "evaluation_target_clamp": {"target": "pkg/state.py:update"},
    }
