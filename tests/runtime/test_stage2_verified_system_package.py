from __future__ import annotations

import json
from pathlib import Path

from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.greenfield_scaffold import create_greenfield_scaffold, run_project_verification
from runtime.greenfield_templates import acceptance_covered
from runtime.programmer_project_review import review_programmer_project
from runtime.stage2_template_admission import run_stage2_template_admission
from runtime.stage2_debug_loop import run_stage2_debug_loop
from runtime.verified_system_package import build_verified_system_package


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
    assert report["tester_review"]["recommendation"] == "approve"
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
    assert report["semantic_hypothesis_proposal"]["hypothesis_type"] == "new_template_candidate"
    assert report["l4_semantic_validation"]["artifact_type"] == "L4SemanticValidationResult"
    assert report["l4_semantic_validation"]["status"] == "accepted"
    assert report["l4_semantic_validation"]["accepted_action"] == "record_template_backlog"
    assert report["l4_semantic_validation"]["decision"]["backlog_allowed"] is True
    assert report["stage2_template_backlog_item"]["artifact_type"] == "Stage2TemplateBacklogItem"
    assert report["stage2_template_backlog_item"]["template_id"] == "new_stage2_cli_template"
    assert report["stage2_template_backlog_item"]["requires_human_review"] is True


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
