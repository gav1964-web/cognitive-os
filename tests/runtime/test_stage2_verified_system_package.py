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
        (
            "Напиши CLI-утилиту без внешних зависимостей, которая ищет duplicate файлы в каталоге и сохраняет JSON отчет.",
            "duplicate_file_finder",
            "src/duplicate_finder/finder.py",
        ),
        (
            "Напиши CLI-утилиту без внешних зависимостей, которая строит план пакетного переименования файлов в каталоге по заданному prefix, поддерживает dry-run, сохраняет JSON-отчет, имеет README и тесты.",
            "batch_renamer_cli",
            "src/batch_renamer/renamer.py",
        ),
        (
            "Напиши CLI-утилиту без внешних зависимостей, которая принимает base.json и override.json, детерминированно объединяет вложенные JSON-объекты, сохраняет merged JSON, имеет README и тесты.",
            "json_config_merger",
            "src/json_config_merger/merger.py",
        ),
        (
            "Напиши CLI-утилиту без внешних зависимостей, которая принимает input path каталога статического сайта, сканирует HTML файлы, извлекает title и links, сохраняет JSON-индекс в ./site_index.json, имеет README и тесты.",
            "static_site_indexer",
            "src/static_site_indexer/indexer.py",
        ),
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


def test_sandbox_attempt_spec_blocks_non_allowlisted_case(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    spec = build_sandbox_attempt_spec(
        prompt="напиши GUI приложение",
        semantic_proposal={
            "artifact_type": "SemanticHypothesisProposal",
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {"resolution_id": "map_to_existing_desktop_gui", "actions": ["record_successful_resolution_candidate"]},
            "evidence_refs": ["model_guess"],
        },
        case_name="desktop_gui_app",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
    )

    assert spec["status"] == "blocked"
    assert "case_not_allowlisted:desktop_gui_app" in spec["validation"]["violations"]
    assert spec["invariants"]["sandbox_only"] is True
    assert "run_arbitrary_shell" in spec["forbidden_operations"]


def test_sandbox_attempt_spec_allows_bounded_adapter_recipe(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    spec = build_sandbox_attempt_spec(
        prompt="напиши конвертер .md в .rtf",
        semantic_proposal={
            "artifact_type": "SemanticHypothesisProposal",
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {
                "resolution_id": "map_to_bounded_adapter_recipe_generic_file_converter",
                "actions": ["record_successful_resolution_candidate"],
            },
            "evidence_refs": ["known_templates.generic_file_converter_cli"],
        },
        case_name="generic_file_converter_cli",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
    )

    assert spec["status"] == "ready"
    assert spec["attempt"]["kind"] == "bounded_adapter_recipe"
    assert spec["attempt"]["recipe"]["source_ext"] == ".md"
    assert spec["attempt"]["recipe"]["target_ext"] == ".rtf"
    assert spec["attempt"]["adapter_implementation_plan"]["selected_backend"] == "stdlib_markdown_subset_to_rtf"
    assert spec["attempt"]["library_binding_recipe"]["authority"]["may_install_dependencies"] is False
    assert spec["validation"]["status"] == "ok"
    assert spec["policy"]["source"].endswith("registry/sandbox_attempt_policy.json")
    assert spec["validation"]["policy_source"].endswith("registry/sandbox_attempt_policy.json")


def test_sandbox_attempt_spec_uses_registry_policy_for_allowlist(tmp_path: Path):
    curriculum = tmp_path / "curricula" / "programmer_prompt_stage2"
    (curriculum / "csv_sort_cli").mkdir(parents=True)
    (curriculum / "csv_sort_cli" / "teacher_reference.json").write_text("{}", encoding="utf-8")
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "sandbox_attempt_policy.json").write_text(
        json.dumps(
            {
                "artifact_type": "SandboxAttemptPolicy",
                "schema_version": "0.1",
                "status": "active",
                "allowed_attempt_kinds": {
                    "existing_stage2_case": {"cases": ["csv_sort_cli"], "requires_curriculum_reference": True},
                    "bounded_adapter_recipe": {
                        "cases": [],
                        "requires_curriculum_reference": False,
                        "allowed_backend_prefixes": [],
                        "allowed_backends": [],
                        "required_artifacts": [
                            "GenericFileConversionRecipe",
                            "LibraryBindingRecipe",
                            "AdapterImplementationPlan",
                        ],
                    },
                },
                "runner": {"allowed": ["ProgrammerProjectReview"]},
                "verification_commands": ["python -m compileall -b .", "python -m pytest tests -q"],
                "allowed_operations": [
                    "create_isolated_scaffold",
                    "write_generated_package_files",
                    "run_project_scoped_compileall",
                    "run_project_scoped_pytest",
                    "read_project_scoped_verification",
                ],
                "forbidden_operations": [
                    "edit_user_source_tree",
                    "mutate_registry",
                    "promote_kb_candidate",
                    "run_arbitrary_shell",
                ],
                "required_true_invariants": [
                    "sandbox_only",
                    "existing_case_or_bounded_adapter_recipe_only",
                    "project_scoped_verification_required",
                    "llm_output_is_not_executed",
                ],
                "required_false_invariants": ["source_tree_changes", "registry_changes", "kb_promotion"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    allowed = build_sandbox_attempt_spec(
        prompt="сортируй csv",
        semantic_proposal={
            "artifact_type": "SemanticHypothesisProposal",
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {"resolution_id": "map_to_existing_csv_sort_cli"},
            "evidence_refs": ["known_templates.csv_sort_cli"],
        },
        case_name="csv_sort_cli",
        curriculum_dir=curriculum,
    )
    blocked = build_sandbox_attempt_spec(
        prompt="напиши конвертер .md в .rtf",
        semantic_proposal={
            "artifact_type": "SemanticHypothesisProposal",
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {"resolution_id": "map_to_bounded_adapter_recipe_generic_file_converter"},
            "evidence_refs": ["known_templates.generic_file_converter_cli"],
        },
        case_name="generic_file_converter_cli",
        curriculum_dir=curriculum,
    )

    assert allowed["status"] == "ready"
    assert blocked["status"] == "blocked"
    assert "case_not_allowlisted:generic_file_converter_cli" in blocked["validation"]["violations"]


def test_fallback_autonomy_loop_builds_bounded_adapter_recipe(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    loop = run_fallback_autonomy_loop(
        root=tmp_path,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        prompt="напиши конвертер .md в .rtf",
        semantic_proposal={
            "artifact_type": "SemanticHypothesisProposal",
            "status": "ok",
            "hypothesis_type": "successful_existing_resolution",
            "proposal": {
                "resolution_id": "map_to_bounded_adapter_recipe_generic_file_converter",
                "means_used": ["known_template:generic_file_converter_cli", "generic_file_conversion_recipe"],
                "actions": ["record_successful_resolution_candidate"],
            },
            "evidence_refs": ["known_templates.generic_file_converter_cli"],
            "risks": ["adapter fidelity is bounded"],
            "return_to_gate": True,
        },
        semantic_validation={"accepted_action": "record_successful_resolution_candidate"},
        write=True,
    )

    assert loop["status"] == "sandbox_verified"
    assert loop["selected_case"] == "generic_file_converter_cli"
    assert loop["sandbox_attempt_spec"]["attempt"]["kind"] == "bounded_adapter_recipe"
    assert loop["sandbox_attempt"]["status"] == "ok"
    assert loop["knowledge_candidate"]["record_type"] == "successful_resolution_candidate"
    assert loop["knowledge_candidate"]["status"] == "collect_more_cases"
    assert loop["knowledge_candidate"]["evidence_policy"]["automatic_self_promotion_forbidden"] is True
    assert Path(loop["knowledge_candidate_path"]).is_file()
    project_dir = Path(loop["sandbox_attempt"]["programmer_artifact"]["project_dir"])
    assert (project_dir / "conversion_recipe.json").is_file()
    assert (project_dir / "adapter_implementation_plan.json").is_file()


def test_verified_system_package_requests_behavior_question_capability(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    report = build_verified_system_package(
        root=tmp_path,
        prompt="Что произойдет, если изображение табличной сметы будет повернуто на 90 градусов?",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=False,
    )

    assert report["status"] == "blocked"
    assert report["prompt_adequacy"]["status"] == "needs_clarification"
    assert report["cognitive_control_plane"]["semantic_escalation"]["l4_5_required"] is True
    assert "behavior_question_uncertainty" in report["cognitive_control_plane"]["semantic_escalation"]["reasons"]
    assert report["semantic_hypothesis_request"]["artifact_type"] == "SemanticHypothesisRequest"
    assert report["semantic_hypothesis_proposal"]["hypothesis_type"] == "developer_improvement_request"
    assert report["l4_semantic_validation"]["accepted_action"] == "record_developer_improvement_request"
    assert report["developer_improvement_request"]["missing_capability"] == "fact_based_behavior_question_answering_capability"


def test_stage2_debug_loop_repairs_controlled_fastapi_error(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_stage2" / "fastapi_csv_aggregator" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="fastapi_csv_aggregator", reference=reference)
    app_path = Path(scaffold["project_dir"]) / "src" / "csv_aggregator_service" / "app.py"
    app_text = app_path.read_text(encoding="utf-8")
    app_text = app_text.replace("from fastapi import FastAPI, HTTPException\n", "from fastapi import FastAPI\n")
    app_text = app_text.replace(
        "    try:\n"
        "        report = aggregate_csv(payload.csv_text)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n",
        "    report = aggregate_csv(payload.csv_text)\n",
    )
    app_path.write_text(app_text, encoding="utf-8")
    verification = run_project_verification(Path(scaffold["project_dir"]))
    scaffold["verification"] = verification
    scaffold["acceptance_covered"] = acceptance_covered("fastapi_csv_aggregator", verification)
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {
        "status": "needs_rework",
        "programmer_artifact": scaffold,
        "tester_review": tester_review,
    }

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    final_review = debug_loop["final_review_run"]["tester_review"]

    assert debug_loop["final_status"] == "ok"
    assert "has_controlled_api_error" in debug_loop["attempts"][0]["failure_analysis"]["failed_checks"]
    assert "repair_fastapi_controlled_400" in debug_loop["attempts"][0]["result"]["applied_actions"]
    assert final_review["recommendation"] == "approve"


def test_stage2_debug_loop_repairs_readme_and_dependency_policy(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_stage2" / "fastapi_csv_aggregator" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="fastapi_csv_aggregator", reference=reference)
    project_dir = Path(scaffold["project_dir"])
    (project_dir / "README.md").write_text("# broken\n", encoding="utf-8")
    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(pyproject.read_text(encoding="utf-8").replace('dependencies = ["fastapi"]', "dependencies = []"), encoding="utf-8")
    scaffold["verification"] = run_project_verification(project_dir)
    scaffold["acceptance_covered"] = acceptance_covered("fastapi_csv_aggregator", scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    applied = debug_loop["attempts"][0]["result"]["applied_actions"]

    assert debug_loop["final_status"] == "ok"
    assert "rewrite_readme_prompt" in applied
    assert "repair_dependency_policy" in applied
    assert debug_loop["final_review_run"]["tester_review"]["checks"]["readme_has_run_command"] is True
    assert debug_loop["final_review_run"]["tester_review"]["checks"]["has_dependency_policy"] is True


def test_stage2_debug_loop_repairs_fastapi_kv_controlled_404(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    reference_path = root / "curricula" / "programmer_prompt_stage2" / "fastapi_kv_store" / "teacher_reference.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=tmp_path, case_name="fastapi_kv_store", reference=reference)
    app_path = Path(scaffold["project_dir"]) / "src" / "kv_store_service" / "app.py"
    app_text = app_path.read_text(encoding="utf-8")
    app_text = app_text.replace("from fastapi import FastAPI, HTTPException\n", "from fastapi import FastAPI\n")
    app_text = app_text.replace(
        "    item = store.get(key)\n"
        "    if item is None:\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return item\n",
        "    item = store.get(key)\n    return item\n",
    )
    app_text = app_text.replace(
        "    if not store.delete(key):\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return {'status': 'deleted', 'key': key}\n",
        "    store.delete(key)\n    return {'status': 'deleted', 'key': key}\n",
    )
    app_path.write_text(app_text, encoding="utf-8")
    scaffold["verification"] = run_project_verification(Path(scaffold["project_dir"]))
    scaffold["acceptance_covered"] = acceptance_covered("fastapi_kv_store", scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}

    debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    applied = debug_loop["attempts"][0]["result"]["applied_actions"]

    assert debug_loop["final_status"] == "ok"
    assert "verification_failed" in debug_loop["attempts"][0]["failure_analysis"]["failure_classes"]
    assert "repair_fastapi_controlled_404" in applied
    assert debug_loop["final_review_run"]["tester_review"]["checks"]["has_controlled_api_error"] is True


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
