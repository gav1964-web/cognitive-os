from __future__ import annotations

from pathlib import Path

from runtime.product_debug_loop import run_product_debug_loop
from runtime.product_slice import build_product_slice_spec
from runtime.verified_system_package import build_verified_system_package


TEXT_STATS_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, "
    "считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты."
)
FASTAPI_KV_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
    "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
    "README, тесты и команду запуска."
)


def test_product_slice_wraps_verified_cli_package(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]

    report = build_product_slice_spec(
        root=tmp_path,
        prompt=TEXT_STATS_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["artifact_type"] == "ProductSliceSpec"
    assert report["stage"] == "Stage 3"
    assert report["status"] == "ok"
    assert report["prompt_adequacy"]["status"] == "ready"
    assert report["release_decision"]["decision"] == "slice_ready"
    assert report["verified_system_package"]["artifact_type"] == "VerifiedSystemPackage"
    assert report["architecture_decision"]["artifact_type"] == "ArchitectureDecisionRecord"
    assert report["requirements"]["artifact_type"] == "RequirementSet"
    assert report["documentation_review"]["status"] == "ok"
    assert report["scenario_verification"]["artifact_type"] == "ScenarioVerification"
    assert len(report["implementation_tasks"]) >= 6
    assert report["task_graph"]["artifact_type"] == "ProductTaskGraph"
    assert report["task_graph"]["edges"]
    assert report["invariants"]["sandbox_only"] is True
    assert report["invariants"]["scenario_rework_is_bounded"] is True
    assert Path(report["product_slice_path"]).is_file()


def test_product_slice_wraps_verified_fastapi_package(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]

    report = build_product_slice_spec(
        root=tmp_path,
        prompt=FASTAPI_KV_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["scope"]["system_type"] == "fastapi_service"
    assert report["release_decision"]["decision"] == "slice_ready"
    assert report["verification"]["tester_recommendation"] == "approve"
    assert report["implementation_tasks"][2]["title"] == "add interface boundary"
    assert report["implementation_tasks"][2]["evidence"]
    assert report["scenario_verification"]["status"] == "covered"
    assert report["product_debug_loop"]["status"] == "not_needed"
    assert report["task_graph"]["critical_path"][-1] == "T6"
    assert report["inputs_outputs"]["inputs"] == ["HTTP JSON item payload", "path key"]
    assert "controlled HTTP 404 response" in report["inputs_outputs"]["outputs"]


def test_product_slice_blocks_vague_prompt(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]

    report = build_product_slice_spec(
        root=tmp_path,
        prompt="сделай что-нибудь полезное",
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )

    assert report["artifact_type"] == "ProductSliceSpec"
    assert report["status"] == "blocked"
    assert report["prompt_adequacy"]["status"] in {"needs_clarification", "unsupported", "too_broad"}
    assert report["release_decision"]["decision"] == "blocked"
    assert report["verified_system_package"]["status"] == "blocked"
    assert report["requirements"]["status"] == "blocked"
    assert report["product_debug_loop"]["status"] == "needs_bounded_rework"


def test_product_debug_loop_repairs_missing_documentation_pack(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    package = build_verified_system_package(
        root=tmp_path,
        prompt=FASTAPI_KV_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    reference = _reference(root, "fastapi_kv_store")
    package["documentation"] = {"readme": None, "run_instructions": [], "verification_summary": None}

    loop = run_product_debug_loop(package=package, reference=reference, max_attempts=1)
    final_package = loop["final_package"]

    assert loop["artifact_type"] == "ProductDebugLoop"
    assert loop["final_status"] == "ok"
    assert loop["attempts"][0]["failure_analysis"]["blockers"] == ["documentation_review"]
    assert "rewrite_readme_from_verified_package" in loop["attempts"][0]["result"]["applied_actions"]
    assert final_package["documentation"]["readme"].endswith("/README.md")
    assert any("uvicorn kv_store_service.app:app" in item for item in final_package["documentation"]["run_instructions"])


def test_product_debug_loop_repairs_missing_scenario_evidence(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    package = build_verified_system_package(
        root=tmp_path,
        prompt=FASTAPI_KV_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    reference = _reference(root, "fastapi_kv_store")
    package["tests"] = dict(package["tests"])
    package["tests"]["covered_acceptance"] = []

    loop = run_product_debug_loop(package=package, reference=reference, max_attempts=1)

    assert loop["final_status"] == "ok"
    assert loop["attempts"][0]["failure_analysis"]["blockers"] == ["scenario_verification"]
    assert "rerun_project_scoped_verification" in [row["type"] for row in loop["attempts"][0]["rework_plan"]["actions"]]
    assert "missing items return a controlled 404 response" in loop["final_package"]["tests"]["covered_acceptance"]


def test_product_debug_loop_repairs_fastapi_api_contract_drift(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    package = build_verified_system_package(
        root=tmp_path,
        prompt=FASTAPI_KV_PROMPT,
        curriculum_dir=root / "curricula" / "programmer_prompt_stage2",
        write=True,
    )
    project_dir = Path(str(package["project_dir"]))
    app_path = project_dir / "src" / "kv_store_service" / "app.py"
    app_path.write_text(
        app_path.read_text(encoding="utf-8").replace("@app.get('/items/{key}')", "@app.get('/broken/{key}')"),
        encoding="utf-8",
    )
    package["verification_report"] = {"status": "failed"}
    package["tester_review"]["checks"]["verification_passed"] = False

    loop = run_product_debug_loop(package=package, reference=_reference(root, "fastapi_kv_store"), max_attempts=1)

    assert loop["final_status"] == "ok"
    assert loop["attempts"][0]["failure_analysis"]["blockers"] == ["api_contract_drift"]
    assert "repair_api_contract_drift" in loop["attempts"][0]["result"]["applied_actions"]
    assert "@app.get('/items/{key}')" in app_path.read_text(encoding="utf-8")


def _reference(root: Path, case_name: str) -> dict[str, object]:
    import json

    path = root / "curricula" / "programmer_prompt_stage2" / case_name / "teacher_reference.json"
    return json.loads(path.read_text(encoding="utf-8"))
