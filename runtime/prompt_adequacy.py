"""Prompt Adequacy Gate for Stage 2 package generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .goal_intake import build_goal_spec


SUPPORTED_SYSTEM_TYPES = {"cli", "file_processing_utility", "small_local_service", "fastapi_service"}


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_prompt_adequacy(prompt: str, *, root_input: dict[str, Any] | None = None) -> PromptAdequacyGate:
    spec = build_goal_spec(prompt, root_input=root_input).to_dict()
    system_type = _system_type(prompt)
    checks = _checks(prompt, spec, system_type)
    missing = [name for name, passed in checks.items() if not passed]
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
        clarification_questions=_questions(missing, spec),
        supported_scope=sorted(SUPPORTED_SYSTEM_TYPES),
    )


def _checks(prompt: str, spec: dict[str, Any], system_type: str | None) -> dict[str, bool]:
    lower = prompt.lower()
    greenfield_ok = spec.get("intent") == "implementation" and system_type in SUPPORTED_SYSTEM_TYPES
    return {
        "goal_understood": spec.get("intent") != "unknown" and (spec.get("status") == "ready" or greenfield_ok),
        "system_type_defined": system_type in SUPPORTED_SYSTEM_TYPES,
        "inputs_defined": bool(spec.get("inputs")) or any(word in lower for word in ("input", "file", "csv", "jsonl", "url", "принимает")),
        "outputs_defined": bool(spec.get("outputs")) and spec.get("outputs") != ["final_report"],
        "constraints_defined": bool(spec.get("constraints")) or _has_dependency_policy(lower),
        "success_criteria_verifiable": bool(spec.get("success_criteria")) and any(word in lower for word in ("test", "тест", "readme", "csv", "json", "report", "отчет")),
        "dependencies_policy_defined": _has_dependency_policy(lower),
        "scope_bounded": not any(word in lower for word in ("любую", "anything", "everything", "полностью всё", "все что нужно")),
    }


def _status(spec: dict[str, Any], system_type: str | None, missing: list[str]) -> tuple[str, str]:
    greenfield_ok = spec.get("intent") == "implementation" and system_type in SUPPORTED_SYSTEM_TYPES
    if spec.get("status") == "needs_clarification" and not greenfield_ok:
        return "needs_clarification", "GOAL_SPEC_NEEDS_CLARIFICATION"
    if system_type is None:
        return "unsupported", "SYSTEM_TYPE_NOT_SUPPORTED_OR_UNCLEAR"
    if "scope_bounded" in missing:
        return "too_broad", "PROMPT_SCOPE_TOO_BROAD"
    if missing:
        return "needs_clarification", "PROMPT_ADEQUACY_MISSING_REQUIRED_FIELDS"
    return "ready", "PROMPT_ADEQUATE"


def _system_type(prompt: str) -> str | None:
    lower = prompt.lower()
    if "fastapi" in lower or "http" in lower or "endpoint" in lower or "служб" in lower:
        return "fastapi_service"
    if "cli" in lower or "утилит" in lower or "command" in lower:
        return "cli"
    if any(word in lower for word in ("csv", "jsonl", "xlsx", "markdown", "file", "файл")):
        return "file_processing_utility"
    if "local service" in lower or "локальн" in lower:
        return "small_local_service"
    return None


def _has_dependency_policy(lower: str) -> bool:
    markers = ("без сети", "no live network", "stdlib", "standard library", "без внешних", "локальн", "dependencies", "зависим")
    return any(marker in lower for marker in markers)


def _questions(missing: list[str], spec: dict[str, Any]) -> list[str]:
    if not missing:
        return []
    questions = list(dict(spec.get("clarification") or {}).get("questions") or [])
    mapping = {
        "system_type_defined": "What bounded system type should be produced: CLI, FastAPI service, file utility, or local service?",
        "inputs_defined": "What are the concrete inputs and their formats?",
        "outputs_defined": "What files, API responses, or reports should be produced?",
        "constraints_defined": "What constraints should apply, including network and dependency policy?",
        "success_criteria_verifiable": "What tests or observable criteria prove the result works?",
        "dependencies_policy_defined": "Are external dependencies allowed, or should the package stay stdlib/local-only?",
        "scope_bounded": "Which narrow first version should be built instead of the broad request?",
    }
    questions.extend(mapping[item] for item in missing if item in mapping)
    return questions[:5]
