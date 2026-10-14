"""Create evaluation corpus tasks with the direct-agent vs Cognitive OS contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationSeedTask:
    task_id: str
    task_class: str
    prompt: str
    success_criteria: list[str]
    constraints: tuple[str, ...] = ()
    expected_inputs: tuple[str, ...] = ()
    input_path: str | None = None
    input_url: str | None = None
    input_revision: str | None = None


DEFAULT_EVALUATION_SEEDS: list[EvaluationSeedTask] = [
    EvaluationSeedTask("task11_image_contents_cli", "cli_utility", "Напиши CLI .py, которая перечислит содержимое картинки.", ["CLI accepts image path", "Output is structured text", "No source tree mutation"]),
    EvaluationSeedTask("task12_rotated_image_table", "cli_utility", "Доработай CLI распознавания табличной картинки: что произойдет, если изображение повернуто на 90 градусов?", ["Rotation behavior is explicit", "Failure mode is tested", "No fabricated OCR claims"]),
    EvaluationSeedTask("task13_xls_to_png_converter", "cli_utility", "Напиши конвертер .xls в .png.", ["Adapter boundary exists", "Missing dependencies are controlled", "Tests run without external files"]),
    EvaluationSeedTask("task14_jpg_to_doc_converter", "cli_utility", "Напиши CLI для конвертации .jpg в .doc.", ["Format ambiguity is surfaced", "Fallback path is explicit", "README documents limitations"]),
    EvaluationSeedTask("task15_uppercase_cli", "cli_utility", "Напиши CLI .py, которая переводит текстовый файл в верхний регистр.", ["Input/output paths", "Deterministic transform", "pytest coverage"]),
    EvaluationSeedTask("task16_project7_analysis", "project_analysis", "Проанализируй Python-проект 7 и дай предложения по развитию.", ["Entrypoints detected", "Evidence refs exist", "Recommendations are project-specific"]),
    EvaluationSeedTask("task17_project10_analysis", "project_analysis", "Проанализируй Python-проект 10 и дай предложения по развитию.", ["Capabilities identified", "State and side effects assessed", "Risks are actionable"]),
    EvaluationSeedTask("task18_kb_gap_resolution", "architecture_hypothesis", "Если KB не знает решения, попробуй решить через LLM и сформируй candidate или developer request.", ["KB miss is recorded", "LLM output is not executed directly", "Next action is explicit"]),
    EvaluationSeedTask("task19_role_directory_extension", "configuration", "Добавь новую роль через справочник ролей без изменения runtime-кода.", ["Role is data-defined", "Gates are contract-based", "No role-specific facade added"]),
    EvaluationSeedTask("task20_prompt_adequacy_gate", "negative", "Сделай что-нибудь полезное с моим проектом.", ["ClarificationPacket or controlled block", "No invented requirements", "No implementation attempt without adequacy"]),
    EvaluationSeedTask(
        "task21_fastapi_durable_jobs", "fastapi_service",
        "Создай локальную FastAPI-службу постановки фоновых заданий: идемпотентная постановка, получение статуса, отмена и восстановление очереди после перезапуска.",
        ["API contract covers create, status and cancel", "Idempotency is tested", "Restart recovery is demonstrated", "Invalid transitions fail explicitly", "README contains exact run and test commands"],
        ("No network services", "SQLite or filesystem persistence only", "Generated package or sandbox only", "No placeholder functions"),
        ("An empty writable workspace",),
    ),
    EvaluationSeedTask(
        "task22_fastapi_event_docs", "documentation",
        "Проведи evidence-based аудит документации проекта и подготовь улучшенный README для нового разработчика без изменения исходного кода.",
        ["Commands and entrypoints are verified against source", "Configuration and dependencies are documented", "At least one minimal working example is included", "Unknown behavior is not invented", "Only documentation artifacts are produced"],
        ("No network", "Treat the input tree as read-only", "Cite source paths for non-obvious claims"),
        ("Frozen Python project tree",),
        "artifacts/hypothesis_holdouts/hvp_a78713cac804/src/teamhide__fastapi-event",
        "https://github.com/teamhide/fastapi-event.git", "4e8502e5f1e6744ba7089c359f84e2fb5f5f263d",
    ),
    EvaluationSeedTask(
        "task23_supervisord_docs", "documentation",
        "Восстанови фактический пользовательский контракт проекта и подготовь README с установкой, конфигурацией, примером и диагностикой ошибок.",
        ["Documented behavior matches implementation", "Installation and configuration are reproducible", "Example uses the real public interface", "Failure modes are evidence-backed", "Source tree remains unchanged"],
        ("No network", "Treat the input tree as read-only", "Do not claim unsupported compatibility"),
        ("Frozen Python project tree",),
        "artifacts/hypothesis_holdouts/hvp_148e197a09f8_r2_w741fe387/src/isca__ordered-startup-supervisord",
        "https://gitlab.com/isca/ordered-startup-supervisord.git", "54e32080e673f1548c5d97ed483805d63754656a",
    ),
    EvaluationSeedTask(
        "task24_msgpack_packaging_change", "sandbox_project_change",
        "В отдельной копии модернизируй packaging-конфигурацию проекта, сохранив публичное поведение, и докажи сборку и установку локальными проверками.",
        ["Change is limited to a sandbox copy", "Build metadata is internally consistent", "Wheel or sdist build is verified", "Existing public imports remain usable", "No placeholder implementation is introduced"],
        ("No network", "Never mutate the frozen input", "Use only locally available build tools", "A controlled block is preferable to fabricated success"),
        ("Frozen Python project tree",),
        "artifacts/hypothesis_holdouts/hvp_e850e54e7010_r2_w57a22fbb/src/MusicScience37Projects__utility-libraries__py-msgpack-rpc",
        "https://gitlab.com/MusicScience37Projects/utility-libraries/py-msgpack-rpc.git", "fe4aa4f3bb126c6ca47be3f8832156122a6598e6",
    ),
    EvaluationSeedTask(
        "task25_amazon_tool_test_change", "sandbox_project_change",
        "В отдельной копии найди один подтверждаемый тестами дефект на границе ввода или конфигурации, исправь его минимально и предоставь regression evidence.",
        ["Defect is tied to concrete source evidence", "A failing regression test precedes or demonstrates the fix", "Patch is minimal and preserves unrelated behavior", "Relevant tests pass", "Frozen input remains unchanged"],
        ("No network", "Never mutate the frozen input", "Do not invent a defect", "Block with evidence if no bounded defect can be established"),
        ("Frozen Python project tree",),
        "artifacts/hypothesis_holdouts/hvp_58668fbf4942_r2_w841e325e/src/amzn__amazon-frustration-free-setup-certification-tool",
        "https://github.com/amzn/amazon-frustration-free-setup-certification-tool.git", "221b7cdc9cdf94a688716a499bf5eb6e87c890df",
    ),
    EvaluationSeedTask(
        "task26_atila_development_analysis", "project_analysis",
        "Проанализируй проект как развиваемый Python-продукт: восстанови архитектуру, найди приоритетные недостатки и предложи проверяемую последовательность развития.",
        ["Architecture and entrypoints cite source evidence", "Risks distinguish facts from hypotheses", "Recommendations are project-specific and prioritized", "Each top action has an acceptance check", "No source mutation occurs"],
        ("No network", "Treat the input tree as read-only", "Do not infer maturity from file counts alone"),
        ("Frozen Python project tree",),
        "artifacts/gitlab_blind_iteration_12_40_20260817/src/skitai__atila",
        "https://gitlab.com/skitai/atila.git", "1c82d9b3730d83bda065677f2faf63487f56a09f",
    ),
]


def ensure_evaluation_corpus(*, root: Path, count: int = 20, write: bool = False) -> dict[str, Any]:
    evaluation_dir = root / "evaluation"
    existing = [path.name for path in sorted(evaluation_dir.glob("task*")) if path.is_dir() and path.name != "task_template"] if evaluation_dir.exists() else []
    seeds = [seed for seed in DEFAULT_EVALUATION_SEEDS if seed.task_id not in existing][
        : max(0, count - len(existing))
    ]
    created = []
    if write:
        evaluation_dir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        task_dir = evaluation_dir / seed.task_id
        if task_dir.name in existing:
            continue
        created.append(seed.task_id)
        if write:
            _write_task(task_dir, seed)
    return {
        "artifact_type": "EvaluationCorpusSeedReport",
        "status": "ok",
        "requested_count": count,
        "existing_count": len(existing),
        "created_count": len(created),
        "created": created,
        "expected_total_after_write": len(existing) + len(created),
        "policy": {
            "direct_agent_vs_cognitive_os": True,
            "teacher_reference_is_ground_truth": False,
            "honest_not_run_metrics_allowed": True,
        },
    }


def _write_task(task_dir: Path, seed: EvaluationSeedTask) -> None:
    (task_dir / "direct_agent").mkdir(parents=True, exist_ok=True)
    (task_dir / "cognitive_os").mkdir(parents=True, exist_ok=True)
    (task_dir / "prompt.md").write_text(_prompt_md(seed), encoding="utf-8")
    (task_dir / "direct_agent" / "README.md").write_text(_route_readme("Direct Agent", seed), encoding="utf-8")
    (task_dir / "cognitive_os" / "README.md").write_text(_route_readme("Cognitive OS", seed), encoding="utf-8")
    (task_dir / "metrics.json").write_text(json.dumps(_metrics(seed), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if seed.input_path:
        input_spec = {
            "kind": "project_tree", "path": seed.input_path,
            "url": seed.input_url, "revision": seed.input_revision,
        }
        (task_dir / "input.json").write_text(
            json.dumps(input_spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (task_dir / "verdict.md").write_text("# Verdict\n\nNot evaluated yet.\n", encoding="utf-8")


def _prompt_md(seed: EvaluationSeedTask) -> str:
    criteria = "\n".join(f"- {item}" for item in seed.success_criteria)
    constraints = "\n".join(f"- {item}" for item in seed.constraints)
    inputs = "\n".join(f"- {item}" for item in seed.expected_inputs)
    return f"""# {seed.task_id}

## Prompt

{seed.prompt}

## Constraints

{constraints}

## Expected Inputs

{inputs}

## Success Criteria

{criteria}
"""


def _route_readme(title: str, seed: EvaluationSeedTask) -> str:
    return f"""# {title}

Status: not run.

Task: `{seed.task_id}`
"""


def _metrics(seed: EvaluationSeedTask) -> dict[str, Any]:
    return {
        "task_id": seed.task_id,
        "task_class": seed.task_class,
        "prompt_hash": "sha256:" + hashlib.sha256(seed.prompt.encode("utf-8")).hexdigest(),
        "routes": {
            "direct_agent": _empty_route(),
            "cognitive_os": _empty_route(),
        },
        "comparison": {
            "winner": "undecided",
            "cognitive_os_advantages": [],
            "direct_agent_advantages": [],
            "no_difference": [],
            "confidence": 0.0,
        },
        "invariants": {
            "same_original_prompt": True,
            "same_constraints": True,
            "manual_corrections_recorded": False,
            "teacher_reference_is_ground_truth": False,
            "source_mutation_detected": False,
        },
        "verdict": "not_evaluated",
    }


def _empty_route() -> dict[str, Any]:
    return {
        "executor": "not_run",
        "model": "not_run",
        "status": "not_run",
        "requirement_coverage": 0.0,
        "missed_requirements": 0,
        "invented_requirements": 0,
        "tests_passed": 0,
        "tests_total": 0,
        "verification_status": "not_run",
        "repair_cycles": 0,
        "runtime_seconds": None,
        "estimated_cost": None,
        "artifact_completeness": 0.0,
        "source_safety_violations": 0,
        "review_blockers": 0,
        "human_correction_minutes": None,
    }
