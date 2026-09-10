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

def test_stage2_debug_loop_repairs_cli_input_output_contract(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_stage2" / "text_stats_cli" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="text_stats_cli", reference=reference)
    cli_path = Path(scaffold["project_dir"]) / "src" / "text_stats" / "cli.py"
    cli_path.write_text(
        "from __future__ import annotations\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    return 0\n",
        encoding="utf-8",
    )
    scaffold["verification"] = run_project_verification(Path(scaffold["project_dir"]))
    scaffold["acceptance_covered"] = acceptance_covered("text_stats_cli", scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    applied = debug_loop["attempts"][0]["result"]["applied_actions"]
    final_checks = debug_loop["final_review_run"]["tester_review"]["checks"]

    assert debug_loop["final_status"] == "ok"
    assert "cli_uses_argparse" in debug_loop["attempts"][0]["failure_analysis"]["failed_checks"]
    assert "repair_cli_entrypoint" in applied
    assert final_checks["cli_uses_argparse"] is True
    assert final_checks["cli_accepts_input_output"] is True


def test_stage2_debug_loop_repairs_text_stats_edge_test(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_stage2" / "text_stats_cli" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="text_stats_cli", reference=reference)
    test_path = Path(scaffold["project_dir"]) / "tests" / "test_core.py"
    test_path.write_text(
        "from text_stats.stats import stats\n\n"
        "def test_stats_counts_text():\n"
        "    assert stats('one two\\nthree')['words'] == 3\n",
        encoding="utf-8",
    )
    scaffold["verification"] = run_project_verification(Path(scaffold["project_dir"]))
    scaffold["acceptance_covered"] = acceptance_covered("text_stats_cli", scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    applied = debug_loop["attempts"][0]["result"]["applied_actions"]

    assert debug_loop["final_status"] == "ok"
    assert "has_negative_or_edge_test" in debug_loop["attempts"][0]["failure_analysis"]["failed_checks"]
    assert "repair_negative_edge_tests" in applied
    assert debug_loop["final_review_run"]["tester_review"]["checks"]["has_negative_or_edge_test"] is True


def test_stage2_debug_loop_repairs_json_log_malformed_edge_test(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_local_10" / "json_log_filter_cli" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="json_log_filter_cli", reference=reference)
    project_dir = Path(scaffold["project_dir"])
    (project_dir / "tests" / "fixtures" / "events.jsonl").write_text(
        '{"level":"INFO","message":"ok"}\n{"level":"ERROR","message":"bad"}\n',
        encoding="utf-8",
    )
    (project_dir / "tests" / "test_core.py").write_text(
        "from json_log_filter.filter import filter_lines\n\n"
        "def test_filter_lines():\n"
        "    rows, _ = filter_lines('tests/fixtures/events.jsonl')\n"
        "    assert rows[0]['message'] == 'bad'\n",
        encoding="utf-8",
    )
    scaffold["verification"] = run_project_verification(project_dir)
    scaffold["acceptance_covered"] = acceptance_covered("json_log_filter_cli", scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    applied = debug_loop["attempts"][0]["result"]["applied_actions"]

    assert debug_loop["final_status"] == "ok"
    assert "has_negative_or_edge_test" in debug_loop["attempts"][0]["failure_analysis"]["failed_checks"]
    assert "repair_negative_edge_tests" in applied
    assert debug_loop["final_review_run"]["tester_review"]["checks"]["has_negative_or_edge_test"] is True
