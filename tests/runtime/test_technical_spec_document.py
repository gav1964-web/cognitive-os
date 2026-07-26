from __future__ import annotations

from runtime.technical_spec_document import render_technical_spec_document


def test_technical_spec_document_renders_human_tz_sections() -> None:
    text = render_technical_spec_document(
        project_report={"project": "demo", "content": {"summary": {"root": "demo"}}},
        architecture_decision={"goal": "Extract parser", "project": "demo"},
        technical_spec={
            "artifact_type": "TechnicalSpec",
            "chosen_architecture_option": "minimal_safe_extraction",
            "scope": ["Prepare parser contract."],
            "requirements": [
                {
                    "id": "REQ-001",
                    "priority": "MUST",
                    "statement": "parser.py:parse must expose a bounded contract.",
                    "source": "parser.py:parse",
                }
            ],
            "extraction_contract": {
                "candidate": "parser.py:parse",
                "candidate_score": 120,
                "selection_reason": "source-backed parser boundary",
                "semantic_quality": {
                    "status": "strong",
                    "score": 94,
                    "reasons": ["candidate name suggests a bounded contract"],
                },
            },
            "work_plan_contract": {
                "status": "ready",
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "name": "parser_contract_slice",
                "goal": "Define parser contract before implementation.",
                "targets": ["parser.py:parse"],
                "obligations": [
                    {
                        "id": "WPC-001",
                        "step": "Define ParserInput and ParserOutput contracts.",
                        "target": "parser.py:parse",
                        "verification": "must be linked to acceptance criteria",
                    }
                ],
            },
            "interface_contracts": [
                {
                    "source": "parser.py:parse",
                    "input_contract": {"text": "str"},
                    "output_contract": {"result": "dict"},
                    "side_effect_policy": {"declared": [], "retry_policy": "safe to retry if pure contract holds"},
                }
            ],
            "data_lifecycle": [
                {
                    "stage": "input",
                    "shape": "raw text",
                    "contract_expectation": "validate before parse",
                    "evidence": "ProjectMapReport",
                }
            ],
            "error_model": [
                {"error": "bad_input", "handling": "return typed error", "source": "parser.py:parse"}
            ],
            "acceptance_criteria": [
                {
                    "id": "AC-001",
                    "criterion": "parser.py:parse returns dict for valid text.",
                    "verification": "pytest",
                    "source": "parser.py:parse",
                }
            ],
            "traceability_table": [
                {"source": "parser.py:parse", "requirement": "contract required", "acceptance_id": "AC-001"}
            ],
            "state_and_replay_policy": [
                {
                    "owner": "execution_inputs",
                    "kind": "reproducibility_state",
                    "lifetime": "scenario_replay",
                    "resume_policy": "persist input",
                }
            ],
            "verification_strategy": {"contract_tests": [], "negative_tests": [], "replay_checks": []},
            "implementation_handoff": {
                "recommended_role": "implementer",
                "expected_output": "ImplementationPlan",
                "patch_scope": ["parser.py:parse"],
            },
            "constraints": ["no source rewrite in spec phase"],
            "non_goals": ["do not rewrite whole project"],
        },
    )

    assert "# Техническое задание" in text
    assert "## Первый рабочий срез" in text
    assert "parser_contract_slice" in text
    assert "## Связанные interface contracts" in text
    assert "parser.py:parse" in text
    assert "## Модель ошибок" in text
    assert "## Критерии приемки" in text
    assert "Семантическое качество: сильный кандидат (94)" in text
    assert "Рекомендуемая роль: implementer" in text


def test_technical_spec_document_explains_inner_contract_vs_workflow_slice() -> None:
    text = render_technical_spec_document(
        project_report={"project": "demo", "content": {"summary": {"root": "demo"}}},
        architecture_decision={"goal": "Extract safe inner capability", "project": "demo"},
        technical_spec={
            "chosen_architecture_option": "minimal_safe_extraction",
            "scope": ["Prepare one capability contract."],
            "extraction_contract": {
                "candidate": "llm_providers.py:build_providers",
                "candidate_score": 124,
                "selection_reason": "pure transform candidate",
                "semantic_quality": {"status": "strong", "score": 100, "reasons": []},
            },
            "work_plan_contract": {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "name": "chat_completion_proxy_slice",
                "goal": "Stabilize request workflow.",
                "targets": ["api_server.py:chat_completions", "api_server.py:_handle_chat_request"],
                "obligations": [
                    {
                        "id": "WPC-001",
                        "step": "Define RequestEnvelope.",
                        "target": "api_server.py:chat_completions",
                        "verification": "review checklist",
                    }
                ],
            },
            "interface_contracts": [],
        },
    )

    assert "целевая функция выбрана как самый безопасный внутренний capability" in text
    assert "первый рабочий срез показывает более широкий пользовательский workflow" in text
