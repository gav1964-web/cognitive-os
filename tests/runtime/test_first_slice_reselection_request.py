from __future__ import annotations

from tests.runtime.first_slice_reselection_request_helpers import *

def test_environment_ready_candidate_is_promoted_within_score_slack():
    missing = _ranked("pkg/adapter.py:run", 80, "missing_external")
    ready = _ranked("pkg/core.py:normalize", 55, "ready")

    ranked = promote_environment_ready_candidate([missing, ready])

    assert ranked[0]["source"] == "pkg/core.py:normalize"
    assert "environment-ready candidate selected" in ranked[0]["reasons"][-1]


def test_environment_ready_candidate_does_not_replace_stronger_semantic_contract():
    missing = _ranked("pkg/domain.py:normalize", 80, "missing_external", semantic_score=100)
    ready = _ranked("runtests.py:lint_main", 75, "ready", semantic_score=92)

    ranked = promote_environment_ready_candidate([missing, ready])

    assert ranked[0]["source"] == "pkg/domain.py:normalize"


def test_spec_writer_execution_cost_penalizes_lifecycle_before_selection():
    score, reasons = execution_cost_adjustment({
        "source": "pkg/cli/base.py:main",
        "snippet": "def main(): print('ready')",
        "target_binding": "function_symbol",
    })

    assert score <= -45
    assert any("cli_runtime_boundary" in reason for reason in reasons)


def test_spec_writer_execution_cost_penalizes_runtime_decorator_factory():
    score, reasons = execution_cost_adjustment({
        "source": "runtime/slots.py:async_slot",
        "kind": "function",
        "snippet": "def async_slot(): ...",
        "unresolved_calls": ["asyncio.create_task"],
    })

    assert score <= -45
    assert any("runtime_decorator_factory" in reason for reason in reasons)


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


def test_reselection_request_rejects_candidate_without_bound_source_body():
    request = build_first_slice_reselection_request(
        {
            "candidate": "pkg/api.py:handle",
            "structural_evidence": {"source_body_available": False},
        },
        {"status": "not_required", "missing_modules": []},
    )

    assert request["status"] == "required"
    assert request["trigger"] == "source_body_not_bound_in_approved_first_slice"


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


def test_architect_reselection_prefers_callable_over_property_accessor(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "adapter.py").write_text(
        "import optional_sdk\n\ndef convert_value(value):\n    return optional_sdk.convert(value)\n",
        encoding="utf-8",
    )
    (package / "core.py").write_text(
        "class Service:\n"
        "    @property\n"
        "    def current_value(self) -> str:\n"
        "        return 'value'\n\n"
        "def normalize(value: str) -> str:\n"
        "    return value.strip()\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    project_report["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "pkg/core.py", "name": "current_value"},
        {"path": "pkg/core.py", "name": "normalize"},
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
    assert resolution["outcome"]["selected_targets"][0] == "pkg/core.py:normalize"
    property_row = next(
        row for row in resolution["outcome"]["candidate_viability"]
        if row["target"] == "pkg/core.py:current_value"
    )
    assert property_row["property_accessor"] is True


def test_architect_reselection_prefers_pure_callable_over_filesystem_write(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "core.py").write_text(
        "from pathlib import Path\n\n"
        "def write_value(value: str, path: str) -> str:\n"
        "    Path(path).write_text(value)\n"
        "    return path\n\n"
        "def normalize(value: str) -> str:\n"
        "    return value.strip()\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    project_report["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "pkg/core.py", "name": "write_value"},
        {"path": "pkg/core.py", "name": "normalize"},
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
    assert resolution["outcome"]["selected_targets"][0] == "pkg/core.py:normalize"


def test_execution_feedback_keeps_configured_semantic_floor(monkeypatch, tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "core.py").write_text(
        "def get_value(value):\n    return value\n",
        encoding="utf-8",
    )
    project_report = _project_report(tmp_path, include_ready=False)
    project_report["answers"]["3_capabilities"]["pure_transforms"] = [
        {"path": "pkg/core.py", "name": "get_value"}
    ]
    adr = _architecture_decision(tmp_path, project_report)
    spec = build_technical_spec(architecture_decision=adr)
    spec["first_slice_reselection_request"] = {
        "status": "required",
        "trigger": "executable_acceptance_rejected",
        "current_target": "pkg/adapter.py:convert_value",
        "blocking_evidence": {},
    }
    monkeypatch.setattr(
        architect_reselection,
        "contract_quality",
        lambda *_args: {
            "semantic_score": 71,
            "semantic_status": "suspicious",
            "contract_shape_score": 100,
        },
    )

    resolution = reselect_architecture_first_slice(
        architecture_decision=adr,
        technical_spec=spec,
        project_report=project_report,
        iteration=1,
    )

    assert resolution["status"] == "exhausted"
    assert resolution["outcome"]["semantic_qualified_candidate_count"] == 0


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


def test_architect_defers_runtime_method_even_with_declared_dependency(tmp_path):
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

    assert resolution["status"] == "exhausted"
    assert resolution["outcome"]["viability_deferred_candidate_count"] == 1
    assert resolution["outcome"]["selected_targets"] == []
