import runtime.architect_first_slice_reselection as architect_reselection
import runtime.configured_role_pipeline as configured_pipeline
from runtime.architect_first_slice_reselection import reselect_architecture_first_slice
from runtime.first_slice_reselection_request import build_first_slice_reselection_request
from runtime.role_source_context import build_source_context
from runtime.spec_writer_target_binding import promote_environment_ready_candidate
from runtime.technical_spec_builder import build_technical_spec


def test_environment_ready_candidate_is_promoted_within_score_slack():
    missing = _ranked("pkg/adapter.py:run", 80, "missing_external")
    ready = _ranked("pkg/core.py:normalize", 55, "ready")

    ranked = promote_environment_ready_candidate([missing, ready])

    assert ranked[0]["source"] == "pkg/core.py:normalize"
    assert "environment-ready candidate selected" in ranked[0]["reasons"][-1]


def test_reselection_request_is_required_without_ready_function_alternative():
    request = build_first_slice_reselection_request(
        {"candidate": "pkg/adapter.py:run"},
        {
            "status": "resolution_required",
            "missing_modules": ["optional_sdk"],
            "ranked_alternatives": [
                {"target": "pkg/other.py:run", "readiness_status": "missing_external"},
                {"target": "pkg/context.py", "readiness_status": "ready"},
            ],
        },
    )

    assert request["status"] == "required"
    assert request["trigger"] == "no_environment_ready_candidate_in_approved_first_slice"
    assert request["authority"] == "architect_reselection_required_no_automatic_scope_expansion"


def test_reselection_request_returns_semantic_block_to_architect():
    request = build_first_slice_reselection_request(
        {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "ranked_candidates": [{"source": "pkg/runtime.py:get_value", "score": 42}],
        },
        {"status": "not_required", "missing_modules": []},
    )

    assert request["status"] == "required"
    assert request["trigger"] == "no_semantically_safe_candidate_in_approved_first_slice"
    assert request["blocking_evidence"]["rejected_candidates"][0]["source"] == "pkg/runtime.py:get_value"


def test_architect_expands_candidate_window_and_rebuilds_ready_spec(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "adapter.py").write_text(
        "import optional_sdk\n\ndef convert_value(value: str) -> str:\n    return optional_sdk.convert(value)\n",
        encoding="utf-8",
    )
    (package / "core.py").write_text(
        "def normalize(value: str) -> str:\n    return value.strip().lower()\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=True)
    adr = _architecture_decision(tmp_path, project_report)
    first_spec = build_technical_spec(architecture_decision=adr)

    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=first_spec,
        project_report=project_report,
        iteration=1,
    )
    second_spec = build_technical_spec(architecture_decision=resolution["architecture_decision"])

    assert first_spec["first_slice_reselection_request"]["status"] == "required"
    assert resolution["status"] == "selected"
    assert resolution["outcome"]["selected_targets"] == ["pkg/core.py:normalize"]
    revised_slice = resolution["architecture_decision"]["first_slice_contract"]
    assert all("pkg/adapter.py:convert_value" not in step for step in revised_slice["steps"])
    assert "pkg/core.py:normalize" in revised_slice["steps"][0]
    acceptance = resolution["architecture_decision"]["spec_writer_brief"]["acceptance_targets"]
    assert acceptance == [
        f"Reselected first slice verifies step {index}: {step}"
        for index, step in enumerate(revised_slice["steps"], start=1)
    ]
    assert second_spec["extraction_contract"]["candidate"] == "pkg/core.py:normalize"
    assert second_spec["first_slice_reselection_request"]["status"] == "not_required"
    assert resolution["architecture_decision"]["architecture_synthesis"]["project_profile"]["archetype"]


def test_architect_reports_exhausted_without_environment_ready_candidate(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "adapter.py").write_text(
        "import optional_sdk\n\ndef convert_value(value: str) -> str:\n    return optional_sdk.convert(value)\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    adr = _architecture_decision(tmp_path, project_report)
    spec = build_technical_spec(architecture_decision=adr)
    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=spec,
        project_report=project_report,
        iteration=1,
    )

    assert resolution["status"] == "exhausted"
    assert resolution["outcome"]["environment_ready_candidate_count"] == 0
    assert resolution["architecture_decision"]["first_slice_reselection_history"][-1]["status"] == "exhausted"


def test_architect_can_reselect_callable_with_manifest_declared_dependency(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "setup.py").write_text(
        "from setuptools import setup\nsetup(install_requires=['optional-sdk'])\n",
        encoding="utf-8",
    )
    (package / "adapter.py").write_text(
        "import optional_sdk\n\ndef convert_value(value: str) -> str:\n"
        "    return optional_sdk.convert(value)\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    adr = _architecture_decision(tmp_path, project_report)
    spec = build_technical_spec(architecture_decision=adr)

    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=spec,
        project_report=project_report,
        iteration=1,
    )

    assert resolution["status"] == "selected"
    assert resolution["outcome"]["environment_ready_candidate_count"] == 0
    assert resolution["outcome"]["declared_dependency_candidate_count"] == 1
    assert resolution["outcome"]["selected_targets"] == ["pkg/adapter.py:convert_value"]
    context = resolution["architecture_decision"]["source_context"]["pkg/adapter.py:convert_value"]
    assert context["dependency_readiness"]["status"] == "manifest_declared"
    assert context["dependency_readiness"]["executable_probe_required"] is True


def test_architect_can_reselect_unique_method_with_declared_dependency(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["optional-sdk"]\n', encoding="utf-8"
    )
    (package / "adapter.py").write_text(
        "import missing_sdk\n\ndef convert_value(value):\n    return missing_sdk.convert(value)\n",
        encoding="utf-8",
    )
    (package / "client.py").write_text(
        "import optional_sdk\n\nclass Client:\n"
        "    def send(self, value: str) -> str:\n        return optional_sdk.convert(value)\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    project_report["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "pkg/client.py", "name": "send"}
    ]
    adr = _architecture_decision(tmp_path, project_report)
    spec = build_technical_spec(architecture_decision=adr)

    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=spec,
        project_report=project_report,
        iteration=1,
    )

    assert resolution["status"] == "selected"
    assert "pkg/client.py:send" in resolution["outcome"]["selected_targets"]


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
        "pkg/adapter.py:JsonAdapter.transform",
        "pkg/adapter.py:CsvAdapter.transform",
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


def _ranked(source: str, score: int, status: str) -> dict:
    return {
        "source": source,
        "score": score,
        "index": 0 if status == "missing_external" else 1,
        "reasons": [],
        "evidence": {"dependency_readiness": {"status": status}},
    }


def _project_report(root, *, include_ready: bool) -> dict:
    pure = [{"path": "pkg/core.py", "name": "normalize"}] if include_ready else []
    return {
        "summary": {"root": root.as_posix()},
        "answers": {
            "3_capabilities": {"pure_transforms": pure},
            "6_runtime_extraction_readiness": {
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [{"capability": "pkg/adapter.py:convert_value"}]
                }
            },
        },
    }


def _architecture_decision(root, project_report: dict) -> dict:
    target = "pkg/adapter.py:convert_value"
    first_slice = {
        "name": "adapter_slice",
        "goal": "Specify one callable.",
        "targets": [target],
        "steps": ["Specify the callable contract."],
    }
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "status": "ok",
        "goal": "Prepare a safe first slice",
        "project": root.as_posix(),
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": first_slice,
        "source_context": build_source_context(
            project_root=root.as_posix(),
            project_report=project_report,
            sources=[target],
        ),
        "spec_writer_brief": {
            "scope": ["Specify one callable."],
            "files_or_symbols": [target],
            "acceptance_targets": ["Callable contract is explicit."],
            "first_slice": first_slice,
        },
        "traceability": [{"source": target, "requirement": "Capability requires TechnicalSpec."}],
    }
