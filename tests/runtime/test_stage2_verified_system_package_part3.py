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
