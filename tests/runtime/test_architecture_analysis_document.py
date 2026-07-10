from __future__ import annotations

from runtime.architecture_analysis_document import render_architecture_analysis_document


def test_architecture_document_supports_current_project_answer_keys() -> None:
    text = render_architecture_analysis_document(
        project_report={
            "project": "demo",
            "content": {
                "summary": {"root": "demo"},
                "answers": {
                    "1_scope": {
                        "main_task": "Serve HTTP API requests.",
                        "supported_scenarios": ["Handle chat requests."],
                    },
                    "2_execution": {
                        "entrypoints": ["app/api/server.py"],
                        "primary_execution_path": ["HTTP request", "route handler", "JSON response"],
                    },
                },
            },
        },
        architecture_decision={
            "goal": "Analyze project",
            "decision_summary": "Summary",
            "chosen_option": {"title": "Extract capability", "reason": "bounded"},
        },
        technical_spec={},
    )

    assert "main_task: Serve HTTP API requests." in text
    assert "entrypoints: app/api/server.py" in text
    assert "primary_execution_path: HTTP request, route handler, JSON response" in text
