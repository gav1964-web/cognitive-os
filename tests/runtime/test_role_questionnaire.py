from __future__ import annotations

from runtime.role_knowledge import ROLE_ORDER
from runtime.role_questionnaire import QUESTION_COUNT_PER_ROLE, build_role_questionnaire_report


def _goal_report() -> dict:
    return {
        "goal_id": "case_demo",
        "goal": "Analyze demo project",
        "execution": {
            "status": "ok",
            "outputs": {
                "project_map_report": {
                    "summary": {
                        "root": "demo",
                        "frameworks": ["FastAPI"],
                        "languages": ["Python"],
                        "entrypoints": ["app/main.py"],
                    },
                    "risks": [{"code": "weak_contract", "severity": "medium"}],
                    "answers": {
                        "1_scope": {
                            "main_task": "Serve a small HTTP API.",
                            "supported_scenarios": ["health check", "submit job"],
                            "inputs": ["HTTP request"],
                            "outputs": ["JSON response"],
                        },
                        "2_execution": {
                            "entrypoints": ["app/main.py"],
                            "primary_execution_path": ["request", "handler", "service", "response"],
                            "central_flow_nodes": [{"path": "app/main.py", "name": "create_app"}],
                        },
                        "3_capabilities": {
                            "atomic_reusable_capabilities": ["app/service.py:normalize"],
                            "pure_transforms": [{"path": "app/service.py", "name": "normalize"}],
                            "too_broad_functions": [{"path": "app/main.py", "name": "handle", "loc": 80}],
                        },
                        "4_contracts_data": {
                            "explicit_schemas": ["RequestModel"],
                            "weak_contract_zones": ["app/service.py:normalize"],
                            "data_structures": ["dict request"],
                        },
                        "5_errors_state_repro": {
                            "error_types": ["bad input"],
                            "minimal_cognitive_loop": ["POST /jobs"],
                        },
                        "6_runtime_extraction_readiness": {
                            "mixed_responsibility_functions": [{"path": "app/main.py", "name": "handle"}],
                            "hidden_orchestrators": [{"path": "app/main.py", "name": "handle"}],
                            "idempotency_risks": [{"target": "app/main.py:handle", "side_effects": ["network"]}],
                            "quarantine_candidates": [{"target": "external_api"}],
                            "process_boundary_candidates": [{"target": "app/main.py:handle"}],
                            "resume_reuse_plan": [{"step": "validated_input"}],
                            "minimal_extraction_plan": {
                                "capabilities_to_extract": [{"capability": "app/service.py:normalize", "why": "pure transform"}]
                            },
                        },
                    },
                },
                "extract_python_structure": {
                    "project_insights": {
                        "external_imports": [{"module": "fastapi", "count": 2}],
                        "test_surface": {"test_files": 2},
                    }
                },
                "extract_runtime_commands": {"commands": ["pytest"]},
            },
        },
    }


def _interpretation() -> dict:
    return {
        "level35_project_signals": {"confidence": "high", "signals": []},
        "analysis_tasks": {"tasks": [{"type": "EXTRACT_CAPABILITY", "target": "app/service.py:normalize"}]},
        "architecture_synthesis": {
            "knowledge": {"matched_rule": "api_service", "matched_because": ["FastAPI detected"]},
            "target_architecture_shape": ["contract-first API service"],
            "confidence": "high",
        },
        "knowledge_gap": None,
        "research_plan": None,
    }


def test_role_questionnaire_contains_all_roles_and_questions():
    report = build_role_questionnaire_report(
        project="demo",
        goal_report=_goal_report(),
        interpretation=_interpretation(),
    )

    assert report["artifact_type"] == "RoleQuestionnaireReport"
    assert report["question_count"] == len(ROLE_ORDER) * QUESTION_COUNT_PER_ROLE
    assert [section["role"] for section in report["roles"]] == list(ROLE_ORDER)
    assert all(section["question_count"] == QUESTION_COUNT_PER_ROLE for section in report["roles"])
    assert report["summary"]["roles_without_full_question_set"] == []
    assert report["policy"]["llm_invoked"] is False
    architect_answers = next(section["answers"] for section in report["roles"] if section["role"] == "architect")
    assert any("contract-first API service" in answer["answer"] for answer in architect_answers)
    assert any("api_service" in answer["answer"] for answer in architect_answers)


def test_role_questionnaire_marks_missing_evidence_as_gap():
    report = build_role_questionnaire_report(project="empty", goal_report={"execution": {"outputs": {}}}, interpretation={})

    gaps = [
        gap
        for section in report["roles"]
        for answer in section["answers"]
        for gap in answer["gaps"]
    ]

    assert "not enough evidence in ProjectMapReport" in gaps
    assert report["summary"]["gap_count"] > 0
