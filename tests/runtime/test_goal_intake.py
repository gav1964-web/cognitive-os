from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.goal_intake import build_goal_spec, merge_clarification, validate_goal_spec
from runtime.schema import SchemaValidationError
from runtime.goal_orchestrator import decide_goal_route
from runtime.registry import CapabilityRegistry


ROOT = Path(__file__).resolve().parents[2]


def test_goal_intake_builds_ready_goal_spec_for_project_analysis():
    spec = build_goal_spec(
        "Analyze project map and produce a short report",
        root_input={"project_dir": "F:/ubuntu/test/map"},
    )

    assert spec.status == "ready"
    assert spec.intent == "analyze_project"
    assert spec.target == "F:/ubuntu/test/map"
    assert "report" in spec.outputs
    assert spec.success_criteria
    assert spec.schema_version == "0.1"
    assert spec.field_confidence["target"] == 0.95
    assert spec.field_confidence["intent"] > 0.8
    assert spec.clarification is None
    validate_goal_spec(spec)


def test_goal_intake_asks_clarification_for_vague_prompt():
    spec = build_goal_spec("help me")

    assert spec.status == "needs_clarification"
    assert spec.clarification is not None
    assert "objective" in spec.clarification.missing
    assert spec.clarification.questions
    assert spec.field_confidence["intent"] == 0.2


def test_goal_intake_merges_clarification_into_effective_goal():
    effective = merge_clarification("help me", "Normalize input text and hash it")
    spec = build_goal_spec(effective)

    assert effective == "Normalize input text and hash it"
    assert spec.status == "ready"
    assert spec.intent == "normalize_and_hash"
    assert spec.field_confidence["success_criteria"] > 0.8


def test_goal_intake_asks_target_for_ambiguous_implementation_prompt():
    spec = build_goal_spec("реализуй все")

    assert spec.status == "needs_clarification"
    assert spec.intent == "implementation"
    assert "target" in spec.clarification.missing


def test_goal_intake_accepts_greenfield_image_contents_cli_prompt():
    spec = build_goal_spec("напиши CLI .py, которая перечислит содержимое картинки")

    assert spec.status == "ready"
    assert spec.intent == "implementation"
    assert "image_path" in spec.inputs
    assert "json" in spec.outputs
    assert "local_python" in spec.constraints
    assert spec.clarification is None


def test_goal_intake_accepts_semantic_cli_argument_program_prompt():
    spec = build_goal_spec("программе как параметры передаются два числа и она должна в терминале вывести их сумму")

    assert spec.status == "ready"
    assert spec.intent == "implementation"
    assert "two_numeric_cli_args" in spec.inputs
    assert "stdout" in spec.outputs
    assert "local_python" in spec.constraints
    assert spec.clarification is None


def test_goal_intake_accepts_three_arg_numeric_cli_expression_prompt():
    spec = build_goal_spec(
        "напиши программу CLI которая принимает три аргумента, первые два перемножает, "
        "результат складывает с третьим и выводит результат, например 22*6+3"
    )

    assert spec.status == "ready"
    assert spec.intent == "implementation"
    assert "three_numeric_cli_args" in spec.inputs
    assert "stdout" in spec.outputs
    assert "local_python" in spec.constraints
    assert spec.clarification is None


def test_goal_intake_accepts_project_change_prompt_with_target():
    spec = build_goal_spec(
        "Доработай проект 12: CLI должна читать изображение табличной сметы и выводить .xlsx, .csv и .xls. Тесты без сети."
    )

    assert spec.status == "ready"
    assert spec.intent == "implementation"
    assert spec.target == "12"
    assert "write" in spec.allowed_actions
    assert "csv" in spec.outputs
    assert "spreadsheet" in spec.outputs


def test_goal_spec_contract_rejects_extra_fields():
    spec = build_goal_spec("Normalize input text and hash it").to_dict()
    spec["extra"] = True

    with pytest.raises(SchemaValidationError):
        validate_goal_spec(spec)


def test_goal_orchestrator_uses_goal_intake_clarification():
    registry = CapabilityRegistry(ROOT)
    registry.reset_from_plugins()

    decision = decide_goal_route("process this", registry)

    assert decision.action == "ASK_CLARIFICATION"
    assert decision.reason_code == "GOAL_INTAKE_MISSING_REQUIRED_FIELDS"
    assert decision.clarification_question


def test_goal_orchestrator_routes_project_fact_questions_to_answer_capability(tmp_path):
    registry = CapabilityRegistry(Path(__file__).resolve().parents[2])
    registry.reset_from_plugins()

    decision = decide_goal_route(
        "Проанализируй проект F:/ubuntu/test/map и ответь: сколько .py файлов больше 300 строк?",
        registry,
        root_input={"path": "F:/ubuntu/test/map"},
    )

    assert decision.action == "PLAN_WITH_L35"
    assert decision.required_capabilities[-1] == "project_fact_questions"


def test_goal_intake_cli_outputs_goal_spec():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "goal_intake.py"),
            "--prompt",
            "List files from $input.path",
            "--input-json",
            json.dumps({"path": "plugins"}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["artifact_type"] == "GoalSpec"
    assert payload["status"] == "ready"
    assert payload["intent"] == "list_files"
    assert payload["target"] == "plugins"


def test_goal_run_report_contains_goal_intake():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "goal_run.py"),
            "--root",
            str(ROOT),
            "--goal",
            "help me",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["goal_intake"]["status"] == "needs_clarification"
    assert payload["level4_decision"]["action"] == "ASK_CLARIFICATION"


def test_goal_run_continues_session_after_clarification():
    initial = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "goal_run.py"),
            "--root",
            str(ROOT),
            "--goal",
            "help me",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    initial_payload = json.loads(initial.stdout)

    clarified = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "goal_run.py"),
            "--root",
            str(ROOT),
            "--goal-id",
            initial_payload["goal_id"],
            "--clarification",
            "Normalize input text and hash it",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(clarified.stdout)

    assert payload["goal_id"] == initial_payload["goal_id"]
    assert payload["goal_intake"]["status"] == "ready"
    assert payload["goal_intake"]["intent"] == "normalize_and_hash"
    assert payload["level4_decision"]["action"] == "PLAN_WITH_L35"
