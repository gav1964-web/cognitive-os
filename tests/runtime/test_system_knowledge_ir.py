from __future__ import annotations

from runtime.contract_registry import ContractRegistry
from runtime.system_knowledge_ir import (
    build_system_knowledge_ir,
    build_system_knowledge_ir_from_dialogue,
    verify_system_knowledge_ir,
)


def test_system_knowledge_ir_builds_from_role_artifacts():
    project_report = {
        "artifact_type": "ProjectMapReport",
        "project": "sample/api",
        "summary": {
            "name": "api",
            "frameworks": ["FastAPI"],
            "entrypoints": ["app.py"],
            "routes": ["/health"],
        },
        "answers": {"1_scope": {"main_task": "Serve health API."}},
    }
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "goal": "Preserve health endpoint.",
        "first_slice_contract": {
            "name": "health_endpoint_slice",
            "targets": ["app.py:health"],
            "acceptance_targets": ["GET /health returns status."],
        },
        "traceability": [{"source": "app.py:health", "target": "health endpoint"}],
    }
    spec = {
        "artifact_type": "TechnicalSpec",
        "interface_contracts": [
            {
                "source": "app.py:health",
                "input_contract": {"request": "GET /health"},
                "output_contract": {"status": "ok payload"},
            }
        ],
        "extraction_contract": {
            "candidate": "app.py:health",
            "contract_family": "http_health_check",
            "input_contract": {"request": "GET /health"},
            "output_contract": {"status": "ok payload"},
        },
        "work_plan_contract": {"name": "health_slice", "targets": ["app.py:health"]},
        "acceptance_criteria": [{"id": "AC1", "criterion": "Health endpoint returns ok."}],
        "traceability_table": [{"source": "app.py:health", "requirement": "AC1"}],
    }

    ir = build_system_knowledge_ir(project_report=project_report, architecture_decision=adr, technical_spec=spec)

    assert ir["artifact_type"] == "SystemKnowledgeIR"
    assert ir["origin"] == "role_artifacts"
    assert ir["purpose"] == "Serve health API."
    assert ir["verification"]["status"] == "ok"
    assert ir["public_interfaces"][0]["name"] == "/health"
    assert ir["behavior_contracts"][0]["source"] == "app.py:health"
    assert ir["architecture_slices"][0]["id"] == "health_endpoint_slice"


def test_system_knowledge_ir_keeps_prompt_dialogue_path():
    ir = build_system_knowledge_ir_from_dialogue(
        prompt="Сделай CLI для подсчета строк.",
        goal_spec={
            "artifact_type": "GoalSpec",
            "intent": "Build line counter CLI.",
            "target": "line_counter",
            "inputs": ["text file"],
            "outputs": ["line count"],
            "success_criteria": ["CLI prints number of lines."],
        },
    )

    assert ir["origin"] == "dialogue"
    assert ir["project_identity"]["name"] == "line_counter"
    assert ir["behavior_contracts"][0]["outputs"] == ["line count"]
    assert ir["verification"]["status"] == "ok"


def test_system_knowledge_ir_infers_surface_contracts_from_project_report():
    ir = build_system_knowledge_ir(
        project_report={
            "artifact_type": "ProjectMapReport",
            "project": "sample/tool",
            "summary": {
                "name": "tool",
                "entrypoints": ["tool/__init__.py"],
                "routes": ["/health"],
            },
        }
    )

    assert ir["verification"]["status"] == "ok"
    assert {row["source"] for row in ir["behavior_contracts"]} == {"/health", "tool/__init__.py"}
    assert all(row["evidence"] == "inferred_from_project_surface" for row in ir["behavior_contracts"])
    assert len(ir["acceptance_tests"]) == 2


def test_system_knowledge_ir_carries_domain_profile_into_inferred_behavior():
    ir = build_system_knowledge_ir(
        project_report={
            "artifact_type": "ProjectMapReport",
            "project": "sample/zarr",
            "summary": {"name": "zarr", "entrypoints": ["src/zarr/__init__.py"]},
            "answers": {
                "1_scope": {
                    "main_task": "Provide chunked array storage.",
                    "domain_profile": {
                        "kind": "scientific_compute_library",
                        "scenario_summary": ["Accept array-like values.", "Return computed arrays."],
                        "input_summary": ["array-like values", "chunk metadata"],
                        "output_summary": ["computed arrays", "validation errors"],
                    },
                }
            },
        }
    )

    behavior = ir["behavior_contracts"][0]

    assert ir["domain_model"]["domain_profile"]["kind"] == "scientific_compute_library"
    assert behavior["contract_family"] == "inferred_scientific_compute_library_entrypoint_surface"
    assert behavior["input_contract"]["call"] == ["array-like values", "chunk metadata"]
    assert "shape, dtype" in behavior["failure_contract"][-1]


def test_system_knowledge_ir_contract_is_registered():
    registry = ContractRegistry({})
    ir = build_system_knowledge_ir_from_dialogue(
        prompt="Build tiny API.",
        goal_spec={
            "intent": "Build tiny API.",
            "target": "tiny_api",
            "inputs": ["HTTP request"],
            "outputs": ["JSON response"],
            "success_criteria": ["Response is JSON."],
        },
    )

    registry.validate_artifact(ir)


def test_system_knowledge_ir_verifier_reports_missing_core_fields():
    result = verify_system_knowledge_ir({"artifact_type": "SystemKnowledgeIR"})

    assert result["status"] == "needs_work"
    assert "purpose" in result["missing"]
