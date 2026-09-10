from __future__ import annotations
import json
from pathlib import Path
import pytest
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.greenfield_scaffold import create_greenfield_scaffold, run_project_verification
from runtime.greenfield_templates import acceptance_covered
from runtime.programmer_project_review import review_programmer_project
from runtime.stage2_template_admission import run_stage2_template_admission
from runtime.stage2_debug_loop import run_stage2_debug_loop
from runtime.verified_system_package import build_verified_system_package
from runtime.sandbox_attempt_spec import build_sandbox_attempt_spec
from runtime.fallback_autonomy_loop import run_fallback_autonomy_loop
PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает JSONL-файл логов, "
    "фильтрует записи уровня ERROR, пропускает malformed строки, сохраняет новый JSONL-файл, "
    "имеет README и тесты."
)
FASTAPI_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая принимает CSV, "
    "валидирует колонки category/value, считает агрегаты по category, сохраняет JSON-отчёт, "
    "имеет README, тесты и команду запуска."
)
TEXT_STATS_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, "
    "считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты."
)
FASTAPI_KV_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
    "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
    "README, тесты и команду запуска."
)
CSV_SORT_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, "
    "сортирует строки по колонке name, сохраняет CSV-файл, имеет README и тесты."
)
OCR_PROMPT = (
    "Напиши локальную CLI-утилиту OCR без сетевых вызовов: вход — путь к изображению PNG/JPG, "
    "выход — распознанный текст в stdout или текстовый файл. Реальные OCR-зависимости допускаются "
    "только как optional dependencies, тесты должны работать без Tesseract через injectable backend. "
    "Нужны README и pytest."
)
IMAGE_CONTENTS_PROMPT = "напиши CLI .py, которая перечислит содержимое картинки"
IMAGE_TABLE_EXCEL_PROMPT = (
    "Напиши CLI .py утилиту: вход - путь к изображению PNG/JPG/WEBP с табличной сметой, "
    "выход - Excel .xlsx файл с тем же именем, строки таблицы распознаются через OCR/text backend, "
    "тесты без сети через injectable backend."
)
XLS_TO_PNG_PROMPT = "напиши конвертер .xls в .png"
MD_TO_RTF_GENERIC_PROMPT = "напиши конвертер .md в .rtf"
SUM_TWO_NUMBERS_PROMPT = "программе как параметры передаются два числа и она должна в терминале вывести их сумму"
IXBT_NEWS_SCRAPER_PROMPT = "создай скрапер новостей с первой страницы ixbt.com и выведи их в .csv файл"
WEB_RESEARCH_SUMMARIZER_PROMPT = (
    "Создай CLI-проект поиска в интернете по фразе: программа принимает поисковую фразу, "
    "получает топ-15 найденных страниц/статей, извлекает из них основной текст и выдает "
    "краткое суммари по найденным статьям с ссылками на источники."
)
WEB_RESEARCH_FASTAPI_PROMPT = (
    "Напиши приложение с интерфейсом FastAPI, которое принимает фразу для поиска в интернете, "
    "выполняет поиск, берет топ 20 найденных страниц, анализирует их содержимое и выдает одно "
    "итоговое суммари с помощью LLM GigaChat через OpenAI-compatible gateway http://127.0.0.1:8000/v1."
)

def test_prompt_adequacy_gate_accepts_bounded_cli_prompt():
    gate = evaluate_prompt_adequacy(PROMPT).to_dict()

    assert gate["artifact_type"] == "PromptAdequacyGate"
    assert gate["status"] == "ready"
    assert gate["system_type"] == "cli"
    assert gate["checks"]["inputs_defined"] is True
    assert gate["checks"]["outputs_defined"] is True
    assert gate["checks"]["dependencies_policy_defined"] is True
    assert gate["checks"]["success_criteria_verifiable"] is True
    assert gate["clarification_questions"] == []


def test_prompt_adequacy_gate_blocks_vague_prompt():
    gate = evaluate_prompt_adequacy("сделай что-нибудь").to_dict()

    assert gate["status"] in {"needs_clarification", "unsupported", "too_broad"}
    assert gate["clarification_questions"]


def test_prompt_adequacy_gate_accepts_short_image_contents_prompt():
    gate = evaluate_prompt_adequacy(IMAGE_CONTENTS_PROMPT).to_dict()

    assert gate["status"] == "ready"
    assert gate["system_type"] == "cli"
    assert gate["checks"]["inputs_defined"] is True
    assert gate["checks"]["outputs_defined"] is True
    assert gate["checks"]["dependencies_policy_defined"] is True


def test_prompt_adequacy_gate_accepts_semantic_cli_argument_program():
    gate = evaluate_prompt_adequacy(SUM_TWO_NUMBERS_PROMPT).to_dict()

    assert gate["status"] == "ready"
    assert gate["system_type"] == "cli"
    assert gate["checks"]["inputs_defined"] is True
    assert gate["checks"]["outputs_defined"] is True
    assert gate["checks"]["dependencies_policy_defined"] is True
    assert gate["clarification_questions"] == []


def test_prompt_adequacy_gate_accepts_bounded_ixbt_scraper_prompt():
    gate = evaluate_prompt_adequacy(IXBT_NEWS_SCRAPER_PROMPT).to_dict()

    assert gate["status"] == "ready"
    assert gate["system_type"] == "cli"
    assert gate["checks"]["inputs_defined"] is True
    assert gate["checks"]["outputs_defined"] is True
    assert gate["checks"]["dependencies_policy_defined"] is True


def test_prompt_adequacy_gate_classifies_news_site_scraper_url_as_cli():
    gate = evaluate_prompt_adequacy("создай скрапер новостей с первой страницы https://3dnews.ru/ и выведи их в .csv файл").to_dict()

    assert gate["status"] == "ready"
    assert gate["system_type"] == "cli"


def test_verified_system_package_builds_release_artifact(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_10",
        write=True,
    )

    assert report["artifact_type"] == "VerifiedSystemPackage"
    assert report["status"] == "ok"
    assert report["prompt_adequacy"]["status"] == "ready"
    assert report["cognitive_control_plane"]["mode"] == "prompt_to_product"
    assert report["cognitive_control_plane"]["role_transition"]["next_action"] == "build_verified_system_package"
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is False
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["programmer_sandbox_gate"]["status"] == "passed"
    assert report["programmer_sandbox_gate"]["checks"]["source_tree_unchanged"] is True
    assert report["tester_review"]["recommendation"] == "approve"
    assert report["rule_trace"]["artifact_type"] == "RuleTrace"
    assert report["rule_trace"]["step_count"] >= 3
    assert any(step["source"] == "config/l4_decision_rules.json" for step in report["rule_trace"]["steps"])
    assert report["tests"]["missing_acceptance"] == []
    assert report["documentation"]["readme"].endswith("/README.md")
    assert report["invariants"]["direct_user_source_modification"] is False
    assert Path(report["project_dir"]).is_dir()
    assert Path(report["package_report_path"]).is_file()


def test_verified_system_package_builds_fastapi_csv_service(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=FASTAPI_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    checks = report["tester_review"]["checks"]

    assert report["status"] == "ok"
    assert report["system_type"] == "fastapi_service"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["status"] == "passed"
    assert report["release_decision"]["decision"] == "release_ready"
    assert checks["has_fastapi_app"] is True
    assert checks["has_api_tests"] is True
    assert checks["has_controlled_api_error"] is True
    assert report["tests"]["missing_acceptance"] == []
    assert (Path(report["project_dir"]) / "src" / "csv_aggregator_service" / "app.py").is_file()


def test_verified_system_package_builds_text_stats_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=TEXT_STATS_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert (Path(report["project_dir"]) / "src" / "text_stats" / "stats.py").is_file()


def test_verified_system_package_builds_fastapi_kv_store(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=FASTAPI_KV_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    checks = report["tester_review"]["checks"]

    assert report["status"] == "ok"
    assert report["system_type"] == "fastapi_service"
    assert report["release_decision"]["decision"] == "release_ready"
    assert checks["has_fastapi_app"] is True
    assert checks["has_api_tests"] is True
    assert checks["has_controlled_api_error"] is True
    assert report["tests"]["missing_acceptance"] == []
    assert (Path(report["project_dir"]) / "src" / "kv_store_service" / "store.py").is_file()


def test_verified_system_package_builds_csv_sort_cli_after_template_admission(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=CSV_SORT_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is False
    assert (Path(report["project_dir"]) / "src" / "csv_sort" / "sorter.py").is_file()


def test_verified_system_package_builds_ixbt_news_scraper(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=IXBT_NEWS_SCRAPER_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_local_10",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "news_site_scraper_cli"
    assert report["tests"]["missing_acceptance"] == []
    assert (Path(report["project_dir"]) / "src" / "news_site_scraper" / "cli.py").is_file()
    assert (Path(report["project_dir"]) / "tests" / "fixtures" / "news_page.html").is_file()


def test_verified_system_package_builds_ixbt_markdown_top10_news_scraper(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="сделай скрапер топ 10 новостей с ixbt.com и выведи в .md",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    project_dir = Path(report["project_dir"])

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["prompt_adequacy"]["status"] == "ready"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "news_site_scraper_cli"
    assert report["tests"]["missing_acceptance"] == []
    assert report["generated_product_quality"]["checks"]["news_scraper_has_per_article_summary"] is True
    assert report["generated_product_quality"]["checks"]["news_scraper_live_top_count_is_contract"] is True
    assert report["generated_product_quality"]["checks"]["news_scraper_live_summary_enrichment"] is True
    assert (project_dir / "src" / "news_site_scraper" / "report_writer.py").is_file()
    assert (project_dir / "src" / "news_site_scraper" / "article_summary.py").is_file()
    assert "write_news_markdown" in (project_dir / "src" / "news_site_scraper" / "report_writer.py").read_text(encoding="utf-8")
    assert "--top" in (project_dir / "src" / "news_site_scraper" / "cli.py").read_text(encoding="utf-8")


def test_verified_system_package_builds_general_news_site_scraper(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="создай скрапер новостей с первой страницы https://3dnews.ru/ и выведи их в .csv файл",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    project_dir = Path(report["project_dir"])

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "news_site_scraper_cli"
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is False
    assert report["tests"]["missing_acceptance"] == []
    assert (project_dir / "src" / "news_site_scraper" / "cli.py").is_file()
    assert (project_dir / "src" / "news_site_scraper" / "site_profile.py").is_file()
    assert (project_dir / "tests" / "fixtures" / "news_page.html").is_file()


def test_verified_system_package_builds_web_research_summarizer(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=WEB_RESEARCH_SUMMARIZER_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    project_dir = Path(report["project_dir"])

    assert report["status"] == "ok"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "web_research_summarizer_cli"
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["tests"]["missing_acceptance"] == []
    assert report["tester_review"]["checks"]["cli_accepts_input_output"] is True
    assert report["generated_product_quality"]["status"] == "passed"
    assert report["generated_product_quality"]["score"] >= 0.92
    assert (project_dir / "src" / "web_research_summarizer" / "cli.py").is_file()
    assert (project_dir / "tests" / "fixtures" / "search_results.json").is_file()


def test_verified_system_package_builds_web_research_fastapi_service(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=WEB_RESEARCH_FASTAPI_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    project_dir = Path(report["project_dir"])

    assert report["status"] == "ok"
    assert report["system_type"] == "fastapi_service"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "web_research_summarizer_fastapi"
    assert report["release_decision"]["decision"] == "release_ready_with_risks"
    assert report["tests"]["missing_acceptance"] == []
    assert report["tester_review"]["checks"]["has_api_tests"] is True
    assert report["generated_product_quality"]["status"] == "passed"
    assert report["generated_product_quality"]["score"] >= 0.92
    assert (project_dir / "src" / "web_research_service" / "app.py").is_file()
    llm_client = (project_dir / "src" / "web_research_service" / "llm_client.py").read_text(encoding="utf-8")
    assert "DEFAULT_BASE_URL = 'http://127.0.0.1:8000/v1'" in llm_client
    assert "DEFAULT_MODEL = 'GigaChat'" in llm_client


def test_verified_system_package_builds_generic_news_scraper_for_unknown_site(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="создай скрапер новостей с сайта https://zindi.africa/ и выведи их в .csv файл",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "news_site_scraper_cli"
    assert report["tests"]["missing_acceptance"] == []
    assert report["generated_product_quality"]["checks"]["news_scraper_live_top_count_is_contract"] is True
    assert (Path(report["project_dir"]) / "src" / "news_site_scraper" / "parser.py").is_file()


def test_verified_system_package_builds_ocr_image_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=OCR_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["system_type"] == "cli"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["tester_review"]["checks"]["has_dependency_policy"] is True
    assert report["tester_review"]["checks"]["has_negative_or_edge_test"] is True
    assert (Path(report["project_dir"]) / "src" / "image_ocr" / "ocr.py").is_file()
