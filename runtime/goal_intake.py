"""Normalize user prompts into GoalSpec or ClarificationPacket."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .schema import validate_payload


GOAL_SPEC_SCHEMA_VERSION = "0.1"
CONFIDENCE_FIELDS = ("intent", "target", "inputs", "outputs", "constraints", "success_criteria", "allowed_actions")

GOAL_SPEC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "artifact_type",
        "schema_version",
        "status",
        "raw_prompt",
        "normalized_prompt",
        "intent",
        "target",
        "inputs",
        "outputs",
        "constraints",
        "success_criteria",
        "allowed_actions",
        "assumptions",
        "ambiguity_score",
        "field_confidence",
        "clarification",
    ],
    "additionalProperties": False,
    "properties": {
        "artifact_type": {"type": "string"},
        "schema_version": {"type": "string"},
        "status": {"type": "string", "enum": ["ready", "needs_clarification"]},
        "raw_prompt": {"type": "string"},
        "normalized_prompt": {"type": "string"},
        "intent": {"type": "string"},
        "target": {"type": ["string", "null"]},
        "inputs": {"type": "array", "items": {"type": "string"}},
        "outputs": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "allowed_actions": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "ambiguity_score": {"type": "number", "minimum": 0, "maximum": 1},
        "field_confidence": {
            "type": "object",
            "required": list(CONFIDENCE_FIELDS),
            "additionalProperties": False,
            "properties": {name: {"type": "number", "minimum": 0, "maximum": 1} for name in CONFIDENCE_FIELDS},
        },
        "clarification": {
            "type": ["object", "null"],
            "required": ["status", "reason_code", "missing", "questions"],
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string"},
                "reason_code": {"type": "string"},
                "missing": {"type": "array", "items": {"type": "string"}},
                "questions": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


@dataclass(frozen=True)
class ClarificationPacket:
    status: str
    reason_code: str
    missing: list[str]
    questions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoalSpec:
    artifact_type: str
    schema_version: str
    status: str
    raw_prompt: str
    normalized_prompt: str
    intent: str
    target: str | None
    inputs: list[str]
    outputs: list[str]
    constraints: list[str]
    success_criteria: list[str]
    allowed_actions: list[str]
    assumptions: list[str]
    ambiguity_score: float
    field_confidence: dict[str, float]
    clarification: ClarificationPacket | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.clarification is None:
            payload["clarification"] = None
        return payload


def build_goal_spec(prompt: str, *, root_input: dict[str, Any] | None = None) -> GoalSpec:
    normalized = " ".join(prompt.strip().split())
    lowered = normalized.lower()
    intent = _intent(lowered)
    inputs = _inputs(normalized, root_input or {})
    outputs = _outputs(lowered)
    allowed_actions = _allowed_actions(lowered)
    constraints = _constraints(lowered)
    success = _success_criteria(intent, lowered, outputs)
    target = _target(normalized, intent, root_input or {})
    missing = _missing_fields(normalized, intent, target, success)
    assumptions = _assumptions(intent, target, inputs, outputs, allowed_actions)
    ambiguity = _ambiguity_score(normalized, missing, assumptions)
    clarification = _clarification(missing, intent, target)
    spec = GoalSpec(
        artifact_type="GoalSpec",
        schema_version=GOAL_SPEC_SCHEMA_VERSION,
        status="needs_clarification" if clarification else "ready",
        raw_prompt=prompt,
        normalized_prompt=normalized,
        intent=intent,
        target=target,
        inputs=inputs,
        outputs=outputs,
        constraints=constraints,
        success_criteria=success,
        allowed_actions=allowed_actions,
        assumptions=assumptions,
        ambiguity_score=ambiguity,
        field_confidence=_field_confidence(
            intent=intent,
            target=target,
            inputs=inputs,
            outputs=outputs,
            constraints=constraints,
            success_criteria=success,
            allowed_actions=allowed_actions,
            missing=missing,
            root_input=root_input or {},
        ),
        clarification=clarification,
    )
    validate_goal_spec(spec)
    return spec


def validate_goal_spec(spec: GoalSpec | dict[str, Any]) -> None:
    payload = spec.to_dict() if isinstance(spec, GoalSpec) else spec
    validate_payload(payload, GOAL_SPEC_SCHEMA, label="GoalSpec")


def merge_clarification(prompt: str, answer: str) -> str:
    normalized = " ".join(prompt.strip().split())
    clarification = " ".join(answer.strip().split())
    if not normalized:
        return clarification
    if not clarification:
        return normalized
    current_spec = build_goal_spec(normalized)
    if current_spec.clarification and "objective" in current_spec.clarification.missing:
        return clarification
    return f"{normalized}\nClarification: {clarification}"


def _intent(goal: str) -> str:
    if any(word in goal for word in ("analyze", "analyse", "scan", "map", "проанализ")) and _mentions_project(goal):
        return "analyze_project"
    if any(word in goal for word in ("translate", "translation", "перев")):
        return "translate_text"
    if "pdf" in goal and any(word in goal for word in ("parse", "extract", "text")):
        return "parse_pdf"
    if any(word in goal for word in ("xlsx", "xls", "spreadsheet", "excel", "csv")) and any(
        word in goal for word in ("convert", "converter", "конверт")
    ):
        return "convert_spreadsheet"
    if "markdown" in goal and ("text" in goal or "rtf" in goal or "rich text" in goal):
        return "convert_markdown"
    if "normalize" in goal and "hash" in goal:
        return "normalize_and_hash"
    if ("link" in goal or "href" in goal) and ("html" in goal or "url" in goal):
        return "extract_links"
    if "list" in goal and "file" in goal:
        return "list_files"
    if any(word in goal for word in ("build", "implement", "create", "сделай", "реализ", "напиши")):
        return "implementation"
    return "unknown"


def _target(prompt: str, intent: str, root_input: dict[str, Any]) -> str | None:
    for key in ("project_dir", "project", "path", "input_path", "url"):
        if root_input.get(key):
            return str(root_input[key])
    path_match = re.search(r"\b[A-Za-z]:[\\/][^\s]+|(?:\.{1,2}[\\/]|/)[^\s]+", prompt)
    if path_match:
        return path_match.group(0).strip(".,:;")
    placeholders = re.findall(r"\$input\.([A-Za-z_][A-Za-z0-9_]*)", prompt)
    if placeholders:
        return "$input." + placeholders[0]
    if intent == "analyze_project":
        words = prompt.split()
        for index, word in enumerate(words):
            if word.lower() in {"project", "проект"} and index + 1 < len(words):
                return words[index + 1].strip(".,:;")
    return None


def _inputs(prompt: str, root_input: dict[str, Any]) -> list[str]:
    values = [f"$input.{name}" for name in re.findall(r"\$input\.([A-Za-z_][A-Za-z0-9_]*)", prompt)]
    values.extend(f"$input.{key}" for key in sorted(root_input) if key not in {item[7:] for item in values})
    return sorted(set(values))


def _outputs(goal: str) -> list[str]:
    outputs = []
    if any(word in goal for word in ("report", "отчет", "analysis", "summary")):
        outputs.append("report")
    if any(word in goal for word in ("json", "file", "файл")):
        outputs.append("file")
    if "csv" in goal:
        outputs.append("csv")
    if "xlsx" in goal or "xls" in goal or "excel" in goal:
        outputs.append("spreadsheet")
    if "rtf" in goal or "rich text" in goal:
        outputs.append("rtf")
    if "hash" in goal:
        outputs.append("hash")
    if "text" in goal:
        outputs.append("text")
    return outputs or ["final_report"]


def _allowed_actions(goal: str) -> list[str]:
    if any(word in goal for word in ("only analyze", "только анализ", "оцен", "посмотри")):
        return ["read", "analyze", "report"]
    if any(word in goal for word in ("implement", "реализ", "исправ", "change", "edit")):
        return ["read", "analyze", "write", "test", "report"]
    return ["read", "analyze", "plan", "report"]


def _constraints(goal: str) -> list[str]:
    constraints = []
    if any(word in goal for word in ("без изменений", "do not change", "read-only", "только анализ")):
        constraints.append("read_only")
    if any(word in goal for word in ("test", "тест", "провер")):
        constraints.append("verify_with_tests")
    return constraints


def _success_criteria(intent: str, goal: str, outputs: list[str]) -> list[str]:
    if intent == "analyze_project":
        return ["project purpose, entrypoints, capabilities, contracts, risks, and next steps are reported"]
    if intent == "implementation":
        return ["requested change is implemented", "tests or verification are reported"]
    if intent == "convert_spreadsheet":
        return ["spreadsheet conversion output file is produced"]
    if "hash" in outputs:
        return ["normalized text and hash are produced"]
    if intent != "unknown":
        return [f"{intent} result is produced"]
    return []


def _missing_fields(prompt: str, intent: str, target: str | None, success: list[str]) -> list[str]:
    missing = []
    lowered = prompt.lower().strip()
    if not lowered or _is_vague(lowered):
        missing.append("objective")
    if intent == "unknown":
        missing.append("intent")
    if intent in {"analyze_project", "parse_pdf", "convert_markdown", "convert_spreadsheet", "extract_links", "list_files", "implementation"} and not target:
        missing.append("target")
    if not success:
        missing.append("success_criteria")
    return sorted(set(missing))


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


def _mentions_project(goal: str) -> bool:
    return "project" in goal or "проект" in goal
