from __future__ import annotations

from runtime.architecture_analysis_document import render_architecture_analysis_document


def test_architecture_document_supports_current_project_answer_keys() -> None:
    text = render_architecture_analysis_document(
        project_report={
            "project": "demo",
            "content": {
                "summary": {"root": "demo"},
                "security_health": {
                    "status": "attention_required",
                    "secret_hit_count": 1,
                    "secret_hit_samples": ["config.json"],
                    "recommendation": "move secrets to environment",
                },
                "answers": {
                    "1_scope": {
                        "main_task": "Serve HTTP API requests.",
                        "supported_scenarios": ["Handle chat requests."],
                    },
                    "2_execution": {
                        "entrypoints": ["app/api/server.py"],
                        "primary_execution_path": ["HTTP request", "route handler", "JSON response"],
                    },
                    "6_runtime_extraction_readiness": {
                        "hidden_orchestrators": [
                            {"path": "app/api/server.py", "name": "handle_chat", "loc": 120}
                        ],
                        "idempotency_risks": [
                            {"target": "app/api/server.py:handle_chat", "side_effects": ["network"]}
                        ],
                        "process_boundary_candidates": [
                            {"path": "app/api/server.py", "name": "call_provider"}
                        ],
                        "data_lifecycle": [
                            {"stage": "input"},
                            {"stage": "validation"},
                            {"stage": "output"},
                        ],
                        "long_lived_state": [
                            {"kind": "cache"}
                        ],
                        "minimal_extraction_plan": {
                            "capabilities_to_extract": [
                                {"capability": "app/core/cache.py:build_key"}
                            ]
                        },
                    },
                },
            },
        },
        architecture_decision={
            "goal": "Analyze project",
            "decision_summary": "Summary",
            "chosen_option": {"title": "Extract capability", "reason": "bounded"},
            "rejected_options": [
                {
                    "id": "full_split",
                    "title": "Full subsystem split",
                    "reason_rejected": "too broad for the first slice",
                    "score_delta": 5,
                    "deferred_until": "after contract tests",
                }
            ],
        },
        technical_spec={},
    )

    assert "# Анализ архитектуры" in text
    assert "Главная задача: Serve HTTP API requests." in text
    assert "Entry points: app/api/server.py" in text
    assert "Основной путь: HTTP-запрос -> route handler -> JSON response" in text
    assert "## Рекомендации по улучшению" in text
    assert "## Отклоненные варианты" in text
    assert "Full subsystem split" in text
    assert "## Security health" in text
    assert "config.json" in text
    assert "## Эскиз целевой архитектуры" in text
    assert "app/api/server.py:handle_chat" in text
    assert "app/core/cache.py:build_key" in text
    assert "Оставить entrypoints тонкими: app/api/server.py." in text
    assert "input -> validation -> output" in text


def test_architecture_document_uses_kb_profile_scope_when_available() -> None:
    text = render_architecture_analysis_document(
        project_report={
            "project": "prompt-lab",
            "content": {
                "summary": {"root": "prompt-lab"},
                "answers": {
                    "1_scope": {
                        "main_task": "Provide a unified OpenAI-compatible gateway for routing chat requests.",
                        "supported_scenarios": ["Accept chat/completion requests."],
                    },
                    "2_execution": {"entrypoints": ["prompt_lab.py"]},
                    "6_runtime_extraction_readiness": {},
                },
            },
        },
        architecture_decision={
            "goal": "Analyze project",
            "chosen_option": {"title": "Extract capability", "reason": "bounded"},
            "architecture_synthesis": {
                "project_profile": {
                    "label": "prompt evaluation and enrichment lab",
                    "knowledge_rule": "prompt_lab_evaluation_runtime",
                    "purpose_summary": "Run a prompt laboratory for repeatable prompt quality experiments.",
                    "scenario_summary": ["Render validation prompts.", "Analyze prompt-lab runs."],
                    "input_summary": ["prompt cases", "templates"],
                    "output_summary": ["run reports", "analysis conclusions"],
                }
            },
        },
        technical_spec={},
    )

    assert "Архитектурный архетип: prompt evaluation and enrichment lab (`prompt_lab_evaluation_runtime`)" in text
    assert "Главная задача: Run a prompt laboratory for repeatable prompt quality experiments." in text
    assert "Provide a unified OpenAI-compatible gateway" not in text
