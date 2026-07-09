from __future__ import annotations

from pathlib import Path

from runtime.product_slice import build_product_slice_spec


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
