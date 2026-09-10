from __future__ import annotations

from pathlib import Path

from runtime.cognitive_os_entry import decide_entry_route, load_cognitive_os_entry_routes, run_cognitive_os


ROOT = Path(__file__).resolve().parents[2]


def test_entry_routes_config_is_loadable():
    routes = load_cognitive_os_entry_routes(str(ROOT / "config" / "cognitive_os_entry_routes.json"))

    assert routes["schema_version"] == "cognitive_os_entry_routes.v1"
    assert "prompt_to_product" in routes["pipeline_contracts"]


def test_entry_decision_routes_fastapi_search_to_prompt_to_product(tmp_path: Path):
    decision = decide_entry_route(
        root=tmp_path,
        prompt="Напиши FastAPI приложение для поиска в интернете по фразе и суммари топ 20 через GigaChat",
    )

    assert decision["pipeline"] == "prompt_to_product"
    assert decision["stage2_case"] == "web_research_summarizer_fastapi"
    assert decision["pipeline_contract"] == "PromptAdequacyGate -> Stage2TemplateRoute -> VerifiedSystemPackage"


def test_entry_decision_routes_planning_mode_to_architect_spec(tmp_path: Path):
    decision = decide_entry_route(root=tmp_path, prompt="Спроектируй сервер для OpenVPN клиента", mode="planning")

    assert decision["pipeline"] == "greenfield_architect_spec"
    assert decision["pipeline_contract"] == "UserPrompt -> ProductArchitectureRecord -> ProductTechnicalSpec"


def test_entry_decision_routes_existing_project_to_foundation_pipeline(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()

    decision = decide_entry_route(root=tmp_path, prompt="проанализировать проект и дать предложения", project_dir=project)

    assert decision["pipeline"] == "project_foundation_analysis"
    assert decision["pipeline_contract"] == "ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec"


def test_unified_entry_runs_prompt_to_product_fastapi_search(tmp_path: Path):
    report = run_cognitive_os(
        root=tmp_path,
        prompt="Напиши приложение с интерфейсом FastAPI, которое ищет в интернете по фразе и делает суммари топ 20 страниц через GigaChat",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["route_decision"]["pipeline"] == "prompt_to_product"
    assert report["route_decision"]["stage2_case"] == "web_research_summarizer_fastapi"
    assert report["pipeline_result"]["status"] == "ok"
    assert report["llm_gateway"]["status"] == "not_configured"
    assert report["invariants"]["single_entrypoint_used"] is True


def test_unified_entry_blocks_when_configured_gateway_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "runtime.cognitive_os_entry.ensure_llm_gateway",
        lambda root: {"status": "failed", "error": "gateway unavailable"},
    )

    report = run_cognitive_os(root=tmp_path, prompt="Спроектируй CLI для обработки CSV")

    assert report["status"] == "blocked"
    assert report["pipeline_result"]["error"] == "gateway unavailable"
    assert report["llm_gateway"]["status"] == "failed"
