"""Greenfield product architecture artifacts from user prompts."""

from __future__ import annotations

from typing import Any

from .greenfield_architecture_patterns import select_greenfield_pattern
from .prompt_adequacy import evaluate_prompt_adequacy
from .role_skill_common import now_iso


def build_product_architecture_record(
    prompt: str,
    *,
    role_id: str = "architect",
    question_mode: str = "continue_with_assumptions",
) -> dict[str, Any]:
    gate = evaluate_prompt_adequacy(prompt).to_dict()
    pattern = select_greenfield_pattern(prompt)
    components = _list(pattern, "components")
    scenarios = _list(pattern, "main_scenarios")
    open_questions = _open_questions(pattern, gate)
    question_policy = _open_question_policy(prompt=prompt, questions=open_questions, mode=question_mode)
    return {
        "artifact_type": "ProductArchitectureRecord",
        "role": role_id,
        "status": _status(gate, question_policy),
        "created_at": now_iso(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "pattern_id": pattern.get("pattern_id"),
        "open_question_policy": question_policy,
        "product_summary": str(pattern.get("product_summary") or ""),
        "system_type": gate.get("system_type") or pattern.get("system_type"),
        "architecture_style": str(pattern.get("architecture_style") or ""),
        "product_output_contract": _product_output_contract(pattern),
        "real_world_edge_cases": _real_world_edge_cases(pattern),
        "components": components,
        "main_scenarios": scenarios,
        "interfaces": _list(pattern, "interfaces"),
        "data_model": _list(pattern, "data_model"),
        "data_lifecycle": _list(pattern, "data_lifecycle"),
        "external_boundaries": _list(pattern, "external_boundaries"),
        "research_hints": _list(pattern, "research_hints"),
        "architecture_options": _list(pattern, "architecture_options"),
        "chosen_architecture_option": _chosen_architecture_option(pattern),
        "security_policy": _list(pattern, "security_policy"),
        "state_and_replay_policy": _list(pattern, "state_and_replay_policy"),
        "risks": _list(pattern, "risks"),
        "non_goals": _list(pattern, "non_goals"),
        "open_questions": open_questions,
        "spec_writer_brief": {
            "scope": _list(pattern, "scope"),
            "target_components": [row["id"] for row in components],
            "primary_contract": dict(pattern.get("primary_contract") or {}),
            "chosen_architecture_option": _chosen_architecture_option(pattern),
            "acceptance_focus": _list(pattern, "acceptance_focus"),
            "constraints": _list(pattern, "constraints"),
            "product_output_contract": _product_output_contract(pattern),
            "real_world_edge_cases": _real_world_edge_cases(pattern),
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }


def _status(gate: dict[str, Any], question_policy: dict[str, Any]) -> str:
    if gate["status"] not in {"ready", "needs_clarification"}:
        return "blocked"
    if question_policy["decision"] == "ask_user_before_spec":
        return "needs_clarification"
    return "ok"


def _open_question_policy(*, prompt: str, questions: list[str], mode: str) -> dict[str, Any]:
    normalized = mode.strip().lower().replace("-", "_")
    if normalized in {"continue", "default"}:
        normalized = "continue_with_assumptions"
    if normalized in {"ask", "ask_user", "clarify"}:
        normalized = "ask_user_before_spec"
    if normalized not in {"continue_with_assumptions", "ask_user_before_spec"}:
        raise ValueError(f"Unsupported greenfield question mode: {mode}")
    decision = "continue_to_spec_writer" if normalized == "continue_with_assumptions" else "ask_user_before_spec"
    return {
        "mode": normalized,
        "decision": decision if questions else "continue_to_spec_writer",
        "default_mode": "continue_with_assumptions",
        "open_question_count": len(questions),
        "clarification_prompt": _clarification_prompt(prompt, questions) if questions else None,
    }


def _clarification_prompt(prompt: str, questions: list[str]) -> str:
    numbered = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    return (
        "Уточни исходный запрос для ArchitectSkill.\n\n"
        f"Исходный prompt:\n{prompt}\n\n"
        "Ответь на вопросы ниже. Если часть решений оставляем на усмотрение системы, так и напиши.\n\n"
        f"{numbered}"
    )


def _open_questions(pattern: dict[str, Any], gate: dict[str, Any]) -> list[str]:
    questions = list(gate.get("clarification_questions") or [])
    questions.extend(str(item) for item in pattern.get("open_questions", []))
    return questions[:8]


def _list(pattern: dict[str, Any], field: str) -> list[Any]:
    value = pattern.get(field)
    return list(value) if isinstance(value, list) else []


def _chosen_architecture_option(pattern: dict[str, Any]) -> dict[str, Any] | None:
    for option in _list(pattern, "architecture_options"):
        if isinstance(option, dict) and option.get("status") == "chosen":
            return dict(option)
    return None


def _product_output_contract(pattern: dict[str, Any]) -> dict[str, Any]:
    primary = dict(pattern.get("primary_contract") or {})
    lifecycle = _list(pattern, "data_lifecycle")
    output_stage = next((row for row in lifecycle if isinstance(row, dict) and row.get("stage") == "output"), {})
    return {
        "primary_output": primary.get("output"),
        "user_visible_shape": dict(output_stage).get("shape"),
        "constraints": _list(pattern, "constraints"),
    }


def _real_world_edge_cases(pattern: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    edge_markers = ("live", "plain", "cyrillic", "unicode", "iri", "noisy", "empty", "malformed", "timeout", "partial")
    scenarios = _list(pattern, "main_scenarios")
    for scenario in _list(pattern, "main_scenarios"):
        if not isinstance(scenario, dict):
            continue
        text = " ".join(str(scenario.get(key, "")) for key in ("id", "description", "success")).lower()
        if any(marker in text for marker in edge_markers):
            result.append(dict(scenario))
    if result:
        return result[:8]
    return [dict(row) for row in scenarios[:3] if isinstance(row, dict)]
