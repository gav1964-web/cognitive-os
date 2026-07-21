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
]


def ensure_evaluation_corpus(*, root: Path, count: int = 20, write: bool = False) -> dict[str, Any]:
    evaluation_dir = root / "evaluation"
    existing = [path.name for path in sorted(evaluation_dir.glob("task*")) if path.is_dir() and path.name != "task_template"] if evaluation_dir.exists() else []
    seeds = DEFAULT_EVALUATION_SEEDS[: max(0, count - len(existing))]
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
    (task_dir / "verdict.md").write_text("# Verdict\n\nNot evaluated yet.\n", encoding="utf-8")


def _prompt_md(seed: EvaluationSeedTask) -> str:
    criteria = "\n".join(f"- {item}" for item in seed.success_criteria)
    return f"""# {seed.task_id}

## Prompt

{seed.prompt}

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
