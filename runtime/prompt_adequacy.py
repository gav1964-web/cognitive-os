"""Prompt Adequacy Gate for Stage 2 package generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .goal_intake import build_goal_spec
from .prompt_boundary_classifier import classify_prompt_boundary
from .prompt_intake_rules import load_prompt_intake_rules, markers


@dataclass(frozen=True)
class PromptAdequacyGate:
    artifact_type: str
    status: str
    reason_code: str
    prompt: str
    system_type: str | None
    goal_spec: dict[str, Any]
    checks: dict[str, bool]
    missing: list[str]
    clarification_questions: list[str]
    supported_scope: list[str]
    boundary_classification: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_prompt_adequacy(prompt: str, *, root_input: dict[str, Any] | None = None) -> PromptAdequacyGate:
    rules = load_prompt_intake_rules()
    spec = build_goal_spec(prompt, root_input=root_input).to_dict()
    system_type = _system_type(prompt, rules=rules)
    checks = _checks(prompt, spec, system_type, rules=rules)
    missing = [name for name, passed in checks.items() if not passed]
    boundary = classify_prompt_boundary(prompt, system_type=system_type, missing=missing).to_dict()
    status, reason = _status(spec, system_type, missing)
    return PromptAdequacyGate(
        artifact_type="PromptAdequacyGate",
        status=status,
        reason_code=reason,
        prompt=prompt,
        system_type=system_type,
        goal_spec=spec,
        checks=checks,
        missing=missing,
        clarification_questions=_questions(missing, spec, rules=rules),
        supported_scope=sorted(str(item) for item in rules["supported_system_types"]),
        boundary_classification=boundary,
    )


def _checks(prompt: str, spec: dict[str, Any], system_type: str | None, *, rules: dict[str, Any]) -> dict[str, bool]:
    lower = prompt.lower()
    supported = set(str(item) for item in rules["supported_system_types"])
    greenfield_ok = spec.get("intent") in {"implementation", "convert_spreadsheet", "file_conversion"} and system_type in supported
    simple_cli_transform = _simple_cli_transform_prompt(lower, rules=rules)
    cli_argument_program = _cli_argument_program_prompt(lower, rules=rules)
    return {
        "goal_understood": spec.get("intent") != "unknown" and (spec.get("status") == "ready" or greenfield_ok),
        "system_type_defined": system_type in supported,
        "inputs_defined": bool(spec.get("inputs"))
        or simple_cli_transform
        or cli_argument_program
        or _has_any_marker(lower, markers("input_markers", rules=rules)),
        "outputs_defined": (bool(spec.get("outputs")) and spec.get("outputs") != ["final_report"])
        or simple_cli_transform
        or cli_argument_program
        or _has_any_marker(lower, markers("output_markers", rules=rules)),
        "constraints_defined": bool(spec.get("constraints")) or _has_dependency_policy(lower, rules=rules),
        "success_criteria_verifiable": simple_cli_transform
        or cli_argument_program
        or (bool(spec.get("success_criteria")) and _has_any_marker(lower, markers("success_criteria_markers", rules=rules))),
        "dependencies_policy_defined": _has_dependency_policy(lower, rules=rules),
        "scope_bounded": not _has_any_marker(lower, markers("scope_unbounded_markers", rules=rules)),
    }


def _status(spec: dict[str, Any], system_type: str | None, missing: list[str]) -> tuple[str, str]:
    supported = set(str(item) for item in load_prompt_intake_rules()["supported_system_types"])
    greenfield_ok = spec.get("intent") in {"implementation", "convert_spreadsheet", "file_conversion"} and system_type in supported
    if spec.get("status") == "needs_clarification" and not greenfield_ok:
        return "needs_clarification", "GOAL_SPEC_NEEDS_CLARIFICATION"
    if system_type is None:
        return "unsupported", "SYSTEM_TYPE_NOT_SUPPORTED_OR_UNCLEAR"
    if "scope_bounded" in missing:
        return "too_broad", "PROMPT_SCOPE_TOO_BROAD"
    if missing:
        return "needs_clarification", "PROMPT_ADEQUACY_MISSING_REQUIRED_FIELDS"
    return "ready", "PROMPT_ADEQUATE"


def _system_type(prompt: str, *, rules: dict[str, Any] | None = None) -> str | None:
    rules = rules or load_prompt_intake_rules()
    lower = prompt.lower()
    if _cli_argument_program_prompt(lower, rules=rules):
        return "cli"
    for row in rules.get("system_type_rules", []):
        if _has_any_marker(lower, [str(item) for item in row.get("markers", [])]):
            return str(row["system_type"])
    return None


def _has_dependency_policy(lower: str, *, rules: dict[str, Any]) -> bool:
    return _has_any_marker(lower, markers("dependency_policy_markers", rules=rules)) or _cli_argument_program_prompt(lower, rules=rules)


def _simple_cli_transform_prompt(lower: str, *, rules: dict[str, Any]) -> bool:
    if not (_has_any_marker(lower, ["cli", "утилит", ".py"]) or _cli_argument_program_prompt(lower, rules=rules)):
        return False
    return _has_any_marker(lower, markers("simple_cli_transform_markers", rules=rules))


def _cli_argument_program_prompt(lower: str, *, rules: dict[str, Any] | None = None) -> bool:
    rules = rules or load_prompt_intake_rules()
    cli_rules = dict(rules.get("cli_argument_program") or {})
    has_program = _has_any_marker(lower, [str(item) for item in cli_rules.get("program_markers", [])])
    has_args = _has_any_marker(lower, [str(item) for item in cli_rules.get("argument_markers", [])])
    has_terminal_output = _has_any_marker(lower, [str(item) for item in cli_rules.get("terminal_output_markers", [])])
    return (has_program or "cli" in lower) and has_args and has_terminal_output


def _questions(missing: list[str], spec: dict[str, Any], *, rules: dict[str, Any]) -> list[str]:
    if not missing:
        return []
    questions = list(dict(spec.get("clarification") or {}).get("questions") or [])
    mapping = dict(rules.get("clarification_questions") or {})
    questions.extend(mapping[item] for item in missing if item in mapping)
    return questions[:5]


def _has_any_marker(lower: str, values: list[str]) -> bool:
    return any(marker in lower for marker in values)
