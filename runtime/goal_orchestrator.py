"""Level 4 goal orchestrator.

The orchestrator chooses a route for a human goal. It does not execute plugins,
mutate registry state, or generate code directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .goal_intake import GoalSpec, build_goal_spec
from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .registry import CapabilityRegistry


LEVEL4_ACTIONS = {"PLAN_WITH_L35", "ASK_CLARIFICATION", "REQUEST_CAPABILITY_SPEC", "STOP_UNSUPPORTED"}


@dataclass(frozen=True)
class GoalDecision:
    action: str
    reason_code: str
    goal: str
    normalized_goal: str
    required_capabilities: list[str]
    missing_capability_hint: str | None = None
    clarification_question: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_goal_route(
    goal: str,
    registry: CapabilityRegistry,
    *,
    root_input: dict[str, Any] | None = None,
) -> GoalDecision:
    goal_spec = build_goal_spec(goal, root_input=root_input)
    if goal_spec.clarification is not None:
        return _clarification_decision(goal, goal_spec)
    normalized = " ".join(goal.strip().lower().split())
    if not normalized:
        return GoalDecision(
            action="ASK_CLARIFICATION",
            reason_code="L4_EMPTY_GOAL",
            goal=goal,
            normalized_goal=normalized,
            required_capabilities=[],
            clarification_question="What concrete result should Cognitive OS produce?",
        )
    if _is_vague(normalized):
        return GoalDecision(
            action="ASK_CLARIFICATION",
            reason_code="L4_GOAL_TOO_VAGUE",
            goal=goal,
            normalized_goal=normalized,
            required_capabilities=[],
            clarification_question="Please specify the input, desired output, and success criterion.",
        )
    if _is_unsafe_or_out_of_scope(normalized):
        return GoalDecision(
            action="STOP_UNSUPPORTED",
            reason_code="L4_UNSUPPORTED_OR_UNSAFE_GOAL",
            goal=goal,
            normalized_goal=normalized,
            required_capabilities=[],
        )

    required = _infer_existing_capabilities(normalized)
    if required and _has_capabilities(registry, required):
        return GoalDecision(
            action="PLAN_WITH_L35",
            reason_code="L4_CAPABILITIES_AVAILABLE",
            goal=goal,
            normalized_goal=normalized,
            required_capabilities=required,
        )

    missing_hint = _missing_capability_hint(normalized)
    if missing_hint:
        return GoalDecision(
            action="REQUEST_CAPABILITY_SPEC",
            reason_code="L4_MISSING_CAPABILITY",
            goal=goal,
            normalized_goal=normalized,
            required_capabilities=required,
            missing_capability_hint=missing_hint,
        )

    return GoalDecision(
        action="PLAN_WITH_L35",
        reason_code="L4_TRY_L35_WITH_REGISTRY",
        goal=goal,
        normalized_goal=normalized,
        required_capabilities=required,
    )


def decide_goal_route_with_llm(
    goal: str,
    registry: CapabilityRegistry,
    *,
    root_input: dict[str, Any] | None = None,
    config: LocalInferenceConfig | None = None,
) -> GoalDecision:
    goal_spec = build_goal_spec(goal, root_input=root_input)
    if goal_spec.clarification is not None:
        return _clarification_decision(goal, goal_spec)
    try:
        result = call_json_chat(_l4_messages(goal, registry, goal_spec=goal_spec), config=config)
        return _sanitize_llm_decision(result, goal, registry)
    except LocalInferenceError:
        return decide_goal_route(goal, registry, root_input=root_input)


def _clarification_decision(goal: str, goal_spec: GoalSpec) -> GoalDecision:
    clarification = goal_spec.clarification
    if clarification is None:
        raise ValueError("GoalSpec has no clarification")
    return GoalDecision(
        action="ASK_CLARIFICATION",
        reason_code=clarification.reason_code,
        goal=goal,
        normalized_goal=goal_spec.normalized_prompt.lower(),
        required_capabilities=[],
        clarification_question=clarification.questions[0] if clarification.questions else None,
    )


def _sanitize_llm_decision(result: dict[str, Any], goal: str, registry: CapabilityRegistry) -> GoalDecision:
    action = str(result.get("action", "")).strip()
    if action not in LEVEL4_ACTIONS:
        raise LocalInferenceError(f"invalid L4 action: {action}")
    normalized_goal = " ".join(goal.strip().lower().split())
    required = [str(item) for item in result.get("required_capabilities", [])]
    reason_code = str(result.get("reason_code", "L4_LLM_DECISION"))
    missing_hint = str(result["missing_capability_hint"]) if result.get("missing_capability_hint") else None
    clarification = str(result["clarification_question"]) if result.get("clarification_question") else None

    if action == "PLAN_WITH_L35":
        if not required:
            required = _infer_existing_capabilities(normalized_goal)
        if required and not _has_capabilities(registry, required):
            return decide_goal_route(goal, registry)
        return GoalDecision(
            action=action,
            reason_code=reason_code,
            goal=goal,
            normalized_goal=normalized_goal,
            required_capabilities=required,
        )
    if action == "ASK_CLARIFICATION":
        if not clarification:
            raise LocalInferenceError("ASK_CLARIFICATION requires clarification_question")
        return GoalDecision(
            action=action,
            reason_code=reason_code,
            goal=goal,
            normalized_goal=normalized_goal,
            required_capabilities=[],
            clarification_question=clarification,
        )
    if action == "REQUEST_CAPABILITY_SPEC":
        if not missing_hint:
            missing_hint = _missing_capability_hint(normalized_goal)
        if not missing_hint:
            raise LocalInferenceError("REQUEST_CAPABILITY_SPEC requires missing_capability_hint")
        return GoalDecision(
            action=action,
            reason_code=reason_code,
            goal=goal,
            normalized_goal=normalized_goal,
            required_capabilities=[],
            missing_capability_hint=missing_hint,
        )
    return GoalDecision(
        action="STOP_UNSUPPORTED",
        reason_code=reason_code,
        goal=goal,
        normalized_goal=normalized_goal,
        required_capabilities=[],
    )


def _has_capabilities(registry: CapabilityRegistry, capability_ids: list[str]) -> bool:
    return all(
        capability_id in registry.capabilities
        and registry.capabilities[capability_id].lifecycle_status in {"active", "degraded"}
        for capability_id in capability_ids
    )


def _infer_existing_capabilities(goal: str) -> list[str]:
    if ("project" in goal or "проект" in goal) and (
        "analyze" in goal or "analyse" in goal or "scan" in goal or "map" in goal or "проанализ" in goal
    ):
        capabilities = [
            "scan_project_tree",
            "detect_project_stack",
            "read_many_files",
            "extract_python_structure",
            "extract_runtime_commands",
            "project_map_report",
        ]
        if _mentions_project_fact_questions(goal):
            capabilities.append("project_fact_questions")
        return capabilities
    if ("normalize" in goal or "normalise" in goal) and "hash" in goal:
        return ["normalize_text", "hash_payload"]
    if "translate" in goal or "translation" in goal:
        return ["translate_text"]
    if "pdf" in goal and ("parse" in goal or "extract" in goal or "text" in goal):
        return ["parse_pdf"]
    if _mentions_spreadsheet_to_csv(goal):
        return ["spreadsheet_to_csv"]
    if _mentions_csv_to_spreadsheet(goal):
        return ["csv_to_spreadsheet"]
    if "markdown" in goal and ("rtf" in goal or "rich text" in goal):
        return ["read_text_file", "markdown_to_rtf", "write_text_file"]
    if "markdown" in goal and ("plain text" in goal or "text file" in goal or "to text" in goal):
        return ["read_text_file", "markdown_to_text", "write_text_file"]
    if ("link" in goal or "href" in goal) and ("html" in goal or "url" in goal or "fetch" in goal):
        return ["fetch_html", "extract_links"]
    if "list" in goal and "file" in goal:
        return ["list_files"]
    return []


def _missing_capability_hint(goal: str) -> str | None:
    if "project" in goal or "проект" in goal:
        return "scan_project_tree"
    if "translate" in goal or "translation" in goal:
        return "translate_text"
    if "pdf" in goal:
        return "parse_pdf"
    if "xlsx" in goal or "xls" in goal or "spreadsheet" in goal or "csv" in goal:
        return "spreadsheet_conversion"
    if "image" in goal or "ocr" in goal:
        return "image_or_ocr_processing"
    if "audio" in goal or "transcribe" in goal:
        return "transcribe_audio"
    return None


def _mentions_project_fact_questions(goal: str) -> bool:
    markers = {
        "answer",
        "question",
        "questions",
        "вопрос",
        "вопросы",
        "ответь",
        "сколько",
        "какие файлы",
        "в каких файлах",
    }
    return any(marker in goal for marker in markers)


def _is_vague(goal: str) -> bool:
    vague_markers = {"do something", "help me", "process this", "handle it", "как-нибудь", "что-нибудь"}
    return len(goal) < 8 or any(marker in goal for marker in vague_markers)


def _is_unsafe_or_out_of_scope(goal: str) -> bool:
    blocked_markers = {"steal", "exfiltrate", "bypass", "delete system", "dump secrets", "credential"}
    return any(marker in goal for marker in blocked_markers)


def _mentions_spreadsheet_to_csv(goal: str) -> bool:
    return "csv" in goal and any(token in goal for token in ("xlsx", "xls", "spreadsheet", "excel")) and "to csv" in goal


def _mentions_csv_to_spreadsheet(goal: str) -> bool:
    return "csv" in goal and any(token in goal for token in ("xlsx", "spreadsheet", "excel")) and (
        "csv to" in goal or "from csv" in goal or "to xlsx" in goal or "to spreadsheet" in goal or "to excel" in goal
    )


def _l4_messages(goal: str, registry: CapabilityRegistry, *, goal_spec: GoalSpec | None = None) -> list[dict[str, str]]:
    catalog = [
        {"id": capability.id, "status": capability.lifecycle_status}
        for capability in sorted(registry.capabilities.values(), key=lambda item: item.id)
        if capability.lifecycle_status in {"active", "degraded"}
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Cognitive OS Level 4. Return only JSON with keys: "
                "action, reason_code, required_capabilities, missing_capability_hint, clarification_question. "
                "action must be one of PLAN_WITH_L35, ASK_CLARIFICATION, REQUEST_CAPABILITY_SPEC, STOP_UNSUPPORTED. "
                "Use GoalSpec as factual input. Treat low field_confidence as uncertainty. "
                "Do not create pipelines. Do not write code. Choose only the route."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\nGoalSpec: {dict(goal_spec.to_dict()) if goal_spec else None}\nAvailable capabilities: {catalog}",
        },
    ]
