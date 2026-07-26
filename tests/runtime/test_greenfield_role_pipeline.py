from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from runtime.greenfield_architecture_patterns import load_greenfield_architecture_patterns, select_greenfield_pattern
from runtime.greenfield_prompt_benchmark import run_greenfield_prompt_benchmark
from runtime.greenfield_role_pipeline import run_greenfield_role_pipeline
from runtime.prompt_adequacy import evaluate_prompt_adequacy


OPENVPN_PROMPT = "создай сервер для работы с клиентом OpenVPN"


def test_prompt_adequacy_accepts_create_server_openvpn_prompt() -> None:
    gate = evaluate_prompt_adequacy(OPENVPN_PROMPT).to_dict()

    assert gate["status"] == "ready"
    assert gate["system_type"] == "small_local_service"
    assert gate["checks"]["goal_understood"] is True


def test_greenfield_role_pipeline_builds_product_architecture_and_spec(tmp_path: Path) -> None:
    report = run_greenfield_role_pipeline(root=tmp_path, prompt=OPENVPN_PROMPT, write=True)

    assert report["status"] == "ok"
    assert report["open_question_policy"]["mode"] == "continue_with_assumptions"
    assert report["next_action"] == "handoff_to_spec_writer"
    assert report["milestone"] == "UserPrompt -> ProductArchitectureRecord -> ProductTechnicalSpec"
    assert report["artifacts"]["product_architecture"]["artifact_type"] == "ProductArchitectureRecord"
    assert report["artifacts"]["product_architecture"]["pattern_id"] == "openvpn_server"
    assert report["artifacts"]["product_technical_spec"]["artifact_type"] == "ProductTechnicalSpec"
    assert report["primary_contract"]["name"] == "ClientProvisionRequest -> ClientProfileResponse"
    assert "CA/OpenVPN" in report["primary_contract"]["side_effect_policy"]
    assert report["safety"]["implementation_started"] is False
    assert Path(report["human_documents"]["product_architecture"]).is_file()
    assert Path(report["human_documents"]["product_technical_spec"]).is_file()

    architecture_text = Path(report["human_documents"]["product_architecture"]).read_text(encoding="utf-8")
    spec_text = Path(report["human_documents"]["product_technical_spec"]).read_text(encoding="utf-8")
    assert "certificate_authority_adapter" in architecture_text
    assert "openvpn_process_adapter" in architecture_text
    assert "Политика открытых вопросов" in architecture_text
    assert "Архитектурное решение" in architecture_text
    assert "Первый полезный срез" in architecture_text
    assert "Допущения до уточнения" in architecture_text
    assert "Техническое задание нового проекта" in spec_text
    assert "Решение для реализации" in spec_text
    assert "Данные и жизненный цикл" in spec_text
    assert "Стратегия проверки" in spec_text
    assert "ClientProvisionRequest -> ClientProfileResponse" in spec_text


def test_greenfield_role_pipeline_can_stop_for_user_clarification(tmp_path: Path) -> None:
    report = run_greenfield_role_pipeline(root=tmp_path, prompt=OPENVPN_PROMPT, write=True, question_mode="ask_user")

    assert report["status"] == "needs_clarification"
    assert report["next_action"] == "ask_user_clarification"
    assert report["open_question_policy"]["decision"] == "ask_user_before_spec"
    assert "Нужен HTTP API, CLI или оба интерфейса?" in report["clarification_prompt"]
    assert report["artifacts"]["product_architecture"]["artifact_type"] == "ProductArchitectureRecord"
    assert report["artifacts"]["product_technical_spec"] is None
    assert "product_technical_spec" not in report["human_documents"]
    assert report["safety"]["spec_writer_started"] is False


def test_greenfield_role_pipeline_escalates_missing_pattern_to_l45_and_developer_request(tmp_path: Path) -> None:
    prompt = "напиши программу cli для расчета фазы луны по переданной дате"

    report = run_greenfield_role_pipeline(root=tmp_path, prompt=prompt, write=True, use_l45_model=False)

    assert report["status"] == "needs_improvement"
    assert report["next_action"] == "record_developer_improvement_request"
    assert report["semantic_gap"]["reason_code"] == "greenfield_pattern_missing"
    assert report["semantic_hypothesis_request"]["artifact_type"] == "SemanticHypothesisRequest"
    assert report["semantic_hypothesis_request"]["layer"] == "L4.5"
    assert report["semantic_hypothesis_proposal"]["hypothesis_type"] == "developer_improvement_request"
    assert report["l4_semantic_validation"]["accepted_action"] == "record_developer_improvement_request"
    assert report["developer_improvement_request"]["artifact_type"] == "DeveloperImprovementRequest"
    assert report["developer_improvement_request"]["requires_developer"] is True
    assert report["artifacts"]["product_architecture"]["pattern_id"] == "generic_product"
    assert report["artifacts"]["product_technical_spec"] is None
    assert "product_technical_spec" not in report["human_documents"]
    assert report["safety"]["spec_writer_started"] is False
    assert report["safety"]["llm_invoked"] is False


def test_greenfield_product_spec_has_unique_requirement_ids() -> None:
    from runtime.greenfield_architecture_builder import build_product_architecture_record
    from runtime.greenfield_spec_builder import build_product_technical_spec

    spec = build_product_technical_spec(build_product_architecture_record(OPENVPN_PROMPT))
    ids = [row["id"] for row in spec["requirements"]]

    assert len(ids) == len(set(ids))


def test_greenfield_patterns_are_loaded_from_config() -> None:
    payload = load_greenfield_architecture_patterns()
    selected = select_greenfield_pattern("создай FastAPI сервис который принимает CSV и возвращает JSON")

    assert payload["schema_version"] == "greenfield_architecture_patterns.v1"
    assert selected["pattern_id"] == "fastapi_csv_aggregator"
    assert any(row["id"] == "aggregation_core" for row in selected["components"])


def test_greenfield_prompt_benchmark_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    report = run_greenfield_prompt_benchmark(root=root)

    assert report["status"] == "ok"
    assert report["summary"]["cases"] >= 20
    assert report["summary"]["failed"] == 0
    assert report["summary"]["avg_score"] == 1.0
    assert report["summary"]["avg_quality_score"] == 1.0
    assert report["summary"]["quality_needs_review"] == 0


def test_verified_system_package_cli_can_run_planning_only(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "verified_system_package.py"),
            "--root",
            str(tmp_path),
            "--prompt",
            OPENVPN_PROMPT,
            "--planning-only",
            "--question-mode",
            "ask_user",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "needs_clarification"
    assert payload["next_action"] == "ask_user_clarification"
    assert payload["artifacts"]["product_technical_spec"] is None
