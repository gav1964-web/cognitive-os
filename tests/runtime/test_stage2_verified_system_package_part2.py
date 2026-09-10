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

def test_verified_system_package_builds_image_contents_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=IMAGE_CONTENTS_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["system_type"] == "cli"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["tester_review"]["checks"]["has_dependency_policy"] is True
    assert report["tester_review"]["checks"]["has_negative_or_edge_test"] is True
    assert (Path(report["project_dir"]) / "src" / "image_contents" / "analyzer.py").is_file()


def test_verified_system_package_builds_image_table_to_excel_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=IMAGE_TABLE_EXCEL_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["system_type"] == "cli"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["tester_review"]["checks"]["has_dependency_policy"] is True
    assert report["tester_review"]["checks"]["has_negative_or_edge_test"] is True
    assert (Path(report["project_dir"]) / "src" / "image_table_excel" / "table_extractor.py").is_file()


@pytest.mark.parametrize(
    ("prompt", "case_name", "expected_file"),
    [
        (IMAGE_CONTENTS_PROMPT, "image_contents_cli", "src/image_contents/analyzer.py"),
        (IMAGE_TABLE_EXCEL_PROMPT, "image_table_to_excel_cli", "src/image_table_excel/table_extractor.py"),
    ],
)
def test_verified_system_package_builds_all_declared_stage2_utility_templates(
    tmp_path: Path,
    prompt: str,
    case_name: str,
    expected_file: str,
):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=prompt,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == case_name
    assert (Path(report["project_dir"]) / expected_file).is_file()


def test_verified_system_package_builds_xls_to_png_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=XLS_TO_PNG_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["system_type"] == "cli"
    assert report["release_decision"]["decision"] == "release_ready"
    assert report["tests"]["missing_acceptance"] == []
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "generic_file_converter_cli"
    assert report["tester_review"]["checks"]["has_dependency_policy"] is True
    assert report["tester_review"]["checks"]["has_negative_or_edge_test"] is True
    project_dir = Path(report["project_dir"])
    binding = json.loads((project_dir / "library_binding_recipe.json").read_text(encoding="utf-8"))

    assert (project_dir / "conversion_recipe.json").is_file()
    assert (project_dir / "library_binding_recipe.json").is_file()
    assert (Path(report["project_dir"]) / "src" / "file_converter_cli" / "converter.py").is_file()
    assert binding["artifact_type"] == "LibraryBindingRecipe"
    assert binding["source_ext"] == ".xls"
    assert binding["target_ext"] == ".png"
    assert binding["authority"]["may_install_dependencies"] is False
    assert {item["backend_id"] for item in binding["candidates"]} >= {
        "libreoffice_headless_render",
        "xlrd_plus_pillow_table_preview",
    }


def test_verified_system_package_uses_generic_recipe_for_another_converter(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=MD_TO_RTF_GENERIC_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    recipe = json.loads((Path(report["project_dir"]) / "conversion_recipe.json").read_text(encoding="utf-8"))
    binding = json.loads((Path(report["project_dir"]) / "library_binding_recipe.json").read_text(encoding="utf-8"))
    plan = json.loads((Path(report["project_dir"]) / "adapter_implementation_plan.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "generic_file_converter_cli"
    assert recipe["source_ext"] == ".md"
    assert recipe["target_ext"] == ".rtf"
    assert {item["backend_id"] for item in binding["candidates"]} >= {"stdlib_markdown_subset_to_rtf", "pandoc_adapter"}
    assert plan["selected_backend"] == "stdlib_markdown_subset_to_rtf"
    assert plan["status"] == "implemented"
    assert report["tests"]["missing_acceptance"] == []


def test_verified_system_package_generic_converter_implements_txt_to_html_backend(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="напиши конвертер .txt в .html",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    project_dir = Path(report["project_dir"])
    plan = json.loads((project_dir / "adapter_implementation_plan.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert plan["selected_backend"] == "stdlib_text_to_html"
    assert plan["status"] == "implemented"
    assert (project_dir / "src" / "file_converter_cli" / "adapters.py").is_file()
    assert report["tests"]["missing_acceptance"] == []


def test_verified_system_package_generic_converter_has_fallback_binding_for_unknown_pair(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="напиши конвертер .foo в .bar",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    binding = json.loads((Path(report["project_dir"]) / "library_binding_recipe.json").read_text(encoding="utf-8"))
    plan = json.loads((Path(report["project_dir"]) / "adapter_implementation_plan.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert binding["candidates"][0]["backend_id"] == "custom_adapter_required"
    assert plan["selected_backend"] == "fixture_adapter"
    assert plan["status"] == "fallback_only"
    assert binding["authority"]["may_call_network"] is False


def test_verified_system_package_understands_short_russian_extension_pair(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="ну давай напишем .jpg в .doc",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    project_dir = Path(report["project_dir"])
    recipe = json.loads((project_dir / "conversion_recipe.json").read_text(encoding="utf-8"))
    plan = json.loads((project_dir / "adapter_implementation_plan.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert report["prompt_adequacy"]["goal_spec"]["intent"] == "file_conversion"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "generic_file_converter_cli"
    assert recipe["source_ext"] == ".jpg"
    assert recipe["target_ext"] == ".doc"
    assert plan["selected_backend"] == "stdlib_image_to_doc_html"
    assert plan["status"] == "implemented"


def test_verified_system_package_uses_output_dir_context_for_format_continuation(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "project12"
    output_dir.mkdir()
    (output_dir / "scaffold_manifest.json").write_text(
        json.dumps(
            {
                "artifact_type": "GreenfieldScaffold",
                "case": "image_table_to_excel_cli",
                "project_dir": output_dir.as_posix(),
                "prompt": IMAGE_TABLE_EXCEL_PROMPT,
            }
        ),
        encoding="utf-8",
    )

    report = build_verified_system_package(
        root=tmp_path,
        prompt="дополняем вывод в .doc",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        output_dir=output_dir,
        write=True,
    )

    assert report["status"] == "ok"
    assert report["prompt"] == "дополняем вывод в .doc"
    assert report["effective_prompt"] != report["prompt"]
    assert report["continuation_context"]["case"] == "image_table_to_excel_cli"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "image_table_to_excel_cli"
    assert report["release_decision"]["decision"] == "release_ready"


def test_verified_system_package_uses_output_dir_context_for_rtf_continuation(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "project12"
    output_dir.mkdir()
    (output_dir / "scaffold_manifest.json").write_text(
        json.dumps(
            {
                "artifact_type": "GreenfieldScaffold",
                "case": "image_table_to_excel_cli",
                "project_dir": output_dir.as_posix(),
                "prompt": IMAGE_TABLE_EXCEL_PROMPT,
            }
        ),
        encoding="utf-8",
    )

    report = build_verified_system_package(
        root=tmp_path,
        prompt="добавить .rtf",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        output_dir=output_dir,
        write=True,
    )

    assert report["status"] == "ok"
    assert ".rtf" in report["effective_prompt"]
    assert report["continuation_context"]["case"] == "image_table_to_excel_cli"
    assert report["cognitive_control_plane"]["prompt_product_gate"]["supported_template"] == "image_table_to_excel_cli"
    assert report["release_decision"]["decision"] == "release_ready"


def test_stage2_template_admission_accepts_csv_sort_cli(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    result = run_stage2_template_admission(
        root=tmp_path,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        case_name="csv_sort_cli",
        write=True,
    )

    assert result["artifact_type"] == "Stage2TemplateAdmissionResult"
    assert result["status"] == "admitted"
    assert result["blockers"] == []
    assert result["invariants"]["admission_does_not_promote_runtime"] is True
    assert Path(result["report_path"]).is_file()


def test_verified_system_package_requests_l45_for_ready_unknown_template(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt=(
            "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, "
            "нормализует значения в колонке name, сохраняет CSV-файл, имеет README и тесты."
        ),
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=False,
    )

    assert report["status"] == "blocked"
    assert report["prompt_adequacy"]["status"] == "ready"
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is True
    assert report["semantic_hypothesis_request"]["artifact_type"] == "SemanticHypothesisRequest"
    assert report["semantic_hypothesis_request"]["layer"] == "L4.5"
    assert report["semantic_hypothesis_request"]["return_path"]["target_layer"] == "L4.0"
    assert report["semantic_evidence_pack"]["artifact_type"] == "SemanticEvidencePack"
    assert report["semantic_evidence_pack"]["authority"]["may_build_package"] is False
    assert report["semantic_hypothesis_proposal"]["artifact_type"] == "SemanticHypothesisProposal"
    assert report["semantic_hypothesis_proposal"]["hypothesis_type"] == "developer_improvement_request"
    assert report["l4_semantic_validation"]["artifact_type"] == "L4SemanticValidationResult"
    assert report["l4_semantic_validation"]["status"] == "accepted"
    assert report["l4_semantic_validation"]["accepted_action"] == "record_developer_improvement_request"
    assert report["developer_improvement_request"]["artifact_type"] == "DeveloperImprovementRequest"
    assert report["developer_improvement_request"]["requires_developer"] is True


def test_verified_system_package_fallback_autonomy_builds_existing_route(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="сделай CLI .py, которая опиши фото",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is True
    assert report["semantic_hypothesis_proposal"]["hypothesis_type"] == "successful_existing_resolution"
    assert report["successful_resolution_candidate"]["resolution_id"] == "map_to_existing_image_contents_cli"
    assert report["fallback_autonomy_loop"]["status"] == "sandbox_verified"
    assert report["fallback_autonomy_loop"]["selected_case"] == "image_contents_cli"
    assert report["fallback_autonomy_loop"]["sandbox_attempt_spec"]["artifact_type"] == "SandboxAttemptSpec"
    assert report["fallback_autonomy_loop"]["sandbox_attempt_spec"]["status"] == "ready"
    assert report["fallback_autonomy_loop"]["sandbox_attempt_spec"]["validation"]["status"] == "ok"
    assert report["fallback_autonomy_loop"]["sandbox_attempt_spec"]["invariants"]["llm_output_is_not_executed"] is True
    assert report["release_decision"]["decision"] == "release_ready"
    assert (Path(report["project_dir"]) / "src" / "image_contents" / "analyzer.py").is_file()
