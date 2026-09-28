from __future__ import annotations

import re
from typing import Any

from runtime.prompt_intake_rules import markers as prompt_markers

def _clarification(missing: list[str], intent: str, target: str | None) -> ClarificationPacket | None:
    if not missing:
        return None
    questions = []
    if "objective" in missing or "intent" in missing:
        questions.append("What concrete result should Cognitive OS produce?")
    if "target" in missing:
        questions.append("What project, file, URL, or input path should be used?")
    if "success_criteria" in missing:
        questions.append("What should count as a successful result?")
    if intent == "implementation" and target is None:
        questions.append("Which repository path or module may be changed?")
    return ClarificationPacket(
        status="needs_clarification",
        reason_code="GOAL_INTAKE_MISSING_REQUIRED_FIELDS",
        missing=missing,
        questions=questions[:3],
    )

def _assumptions(
    intent: str,
    target: str | None,
    inputs: list[str],
    outputs: list[str],
    allowed_actions: list[str],
) -> list[str]:
    assumptions = []
    if target is None and inputs:
        assumptions.append("target will be resolved from runtime input")
    if "write" not in allowed_actions:
        assumptions.append("source and registry mutations require a later explicit decision")
    if outputs == ["final_report"]:
        assumptions.append("human-readable final report is acceptable")
    if intent != "implementation":
        assumptions.append("execution should stay conservative until a plan is reviewed")
    return assumptions

def _ambiguity_score(prompt: str, missing: list[str], assumptions: list[str]) -> float:
    score = len(missing) * 0.35 + len(assumptions) * 0.08
    if len(prompt) < 20:
        score += 0.2
    return round(min(score, 1.0), 3)

def _field_confidence(
    *,
    intent: str,
    target: str | None,
    inputs: list[str],
    outputs: list[str],
    constraints: list[str],
    success_criteria: list[str],
    allowed_actions: list[str],
    missing: list[str],
    root_input: dict[str, Any],
) -> dict[str, float]:
    return {
        "intent": 0.2 if intent == "unknown" else 0.88,
        "target": _target_confidence(target, root_input, missing),
        "inputs": 0.9 if inputs else 0.55,
        "outputs": 0.8 if outputs != ["final_report"] else 0.55,
        "constraints": 0.82 if constraints else 0.5,
        "success_criteria": 0.85 if success_criteria else 0.2,
        "allowed_actions": 0.82 if "write" in allowed_actions else 0.72,
    }

def _target_confidence(target: str | None, root_input: dict[str, Any], missing: list[str]) -> float:
    if "target" in missing:
        return 0.15
    if target is None:
        return 0.35
    if any(str(value) == target for value in root_input.values()):
        return 0.95
    if target.startswith("$input."):
        return 0.8
    if re.match(r"\b[A-Za-z]:[\\/]|(?:\.{1,2}[\\/]|/)", target):
        return 0.9
    return 0.65

def _is_vague(goal: str) -> bool:
    vague_markers = {"help me", "do something", "process this", "handle it", "что-нибудь", "как-нибудь"}
    return len(goal) < 8 or any(marker in goal for marker in vague_markers)

def _is_greenfield_implementation_prompt(goal: str) -> bool:
    has_create_verb = _has_implementation_marker(goal)
    has_product_shape = any(word in goal for word in ("cli", "утилит", "script", ".py", "fastapi", "service", "служб", "сервер"))
    return (has_create_verb and has_product_shape) or _looks_like_cli_program_request(goal)

def _mentions_project(goal: str) -> bool:
    return "project" in goal or "проект" in goal

def _looks_like_project_fact_question(goal: str) -> bool:
    return _mentions_project(goal) and any(marker in goal for marker in prompt_markers("project_fact_question_markers"))

def _has_implementation_marker(goal: str) -> bool:
    return any(marker in goal for marker in prompt_markers("implementation_markers"))

def _looks_like_project_provider_probe(goal: str) -> bool:
    if not _mentions_project(goal):
        return False
    has_server = any(token in goal for token in ("server", "сервер", "gateway", "шлюз"))
    has_probe = any(token in goal for token in ("provider", "providers", "провайдер", "провайдеры", "провайдерами"))
    has_action = any(token in goal for token in ("run", "start", "test", "probe", "запусти", "запустить", "протестируй", "проверь"))
    return has_server and has_probe and has_action

def _looks_like_cli_program_request(goal: str) -> bool:
    has_program = any(word in goal for word in ("программ", "program", "script", "скрипт"))
    has_cli_io = any(word in goal for word in ("параметр", "аргумент", "argument", "parameter", "argv"))
    has_terminal_output = any(word in goal for word in ("терминал", "консоль", "stdout", "print", "вывести", "вывод", "напечат"))
    return (has_program or "cli" in goal) and has_cli_io and has_terminal_output
