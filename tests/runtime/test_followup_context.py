from __future__ import annotations

import json
from pathlib import Path

from runtime.followup_context import resolve_followup_goal


def test_followup_context_resolves_replace_it_from_latest_client_port_report(tmp_path: Path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_old.json").write_text(
        json.dumps(
            {
                "goal_intake": {"target": "F:/ubuntu/test/5.1"},
                "execution": {
                    "outputs": {
                        "project_fact_questions": {
                            "answers": {
                                "client_connection_port": {
                                    "status": "found",
                                    "port": 8000,
                                    "evidence": [{"path": "app/api/server.py", "line": 832}],
                                }
                            }
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    resolved = resolve_followup_goal(tmp_path, "замени его на 9000", {})

    assert resolved is not None
    assert resolved["effective_goal"] == "По проекту F:/ubuntu/test/5.1 замени порт подключения клиентов 8000 на 9000"
    assert resolved["root_input"]["old_value"] == "8000"
    assert resolved["root_input"]["new_value"] == "9000"
    assert resolved["root_input"]["candidate_paths"] == ["app/api/server.py"]


def test_followup_context_resolves_short_question_from_latest_project_report(tmp_path: Path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_recent.json").write_text(
        json.dumps({"goal_intake": {"target": "F:/ubuntu/test/5.1"}, "execution": {"outputs": {}}}),
        encoding="utf-8",
    )

    resolved = resolve_followup_goal(tmp_path, "есть ли автоматический выбор модели при вызове провайдера GigaChat", {})

    assert resolved is not None
    assert resolved["effective_goal"].startswith("По проекту F:/ubuntu/test/5.1 ответь на вопрос:")
    assert resolved["root_input"]["path"] == "F:/ubuntu/test/5.1"
    assert resolved["resolved_reference"]["kind"] == "project_fact_question"


def test_followup_context_resolves_suschestvuet_li_question(tmp_path: Path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_recent.json").write_text(
        json.dumps({"goal_intake": {"target": "F:/ubuntu/test/5.1"}, "execution": {"outputs": {}}}),
        encoding="utf-8",
    )

    resolved = resolve_followup_goal(tmp_path, "существует ли кэш обращений к LLM", {})

    assert resolved is not None
    assert resolved["root_input"]["path"] == "F:/ubuntu/test/5.1"


def test_followup_context_resolves_recommendation_question(tmp_path: Path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_recent.json").write_text(
        json.dumps({"goal_intake": {"target": "F:/ubuntu/test/5.1"}, "execution": {"outputs": {}}}),
        encoding="utf-8",
    )

    resolved = resolve_followup_goal(
        tmp_path,
        "дай рекомендации - имеет ли смысл убрать из кэша признаки модели и провайдера",
        {},
    )

    assert resolved is not None
    assert resolved["root_input"]["path"] == "F:/ubuntu/test/5.1"


def test_followup_context_resolves_project_change_command(tmp_path: Path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_recent.json").write_text(
        json.dumps({"goal_intake": {"target": "F:/ubuntu/test/5.1"}, "execution": {"outputs": {}}}),
        encoding="utf-8",
    )

    resolved = resolve_followup_goal(tmp_path, "убери возможность автовыбора модели у провайдера GigaChat", {})

    assert resolved is not None
    assert resolved["effective_goal"].startswith("По проекту F:/ubuntu/test/5.1 выполни изменение:")
    assert resolved["root_input"]["path"] == "F:/ubuntu/test/5.1"
    assert resolved["root_input"]["recipe_id"] == "disable_gigachat_auto_model"
    assert resolved["resolved_reference"]["kind"] == "project_change"
