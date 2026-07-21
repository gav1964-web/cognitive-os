"""Interpret external role definitions into questionnaire sections."""

from __future__ import annotations

from typing import Any

from . import role_questionnaire_answers as answer_helpers
from .role_definitions import RoleDefinition, load_role_definitions


def build_questionnaire_sections(ctx: Any) -> list[dict[str, Any]]:
    return [_section(definition, ctx) for definition in load_role_definitions()]


def _section(definition: RoleDefinition, ctx: Any) -> dict[str, Any]:
    answers = [_qa(row, ctx) for row in definition.questions]
    return {
        "role": definition.role_id,
        "label": definition.label,
        "question_count": len(answers),
        "consumes": definition.consumes,
        "produces": definition.produces,
        "policy": definition.policy,
        "answers": answers,
    }


def _qa(row: dict[str, Any], ctx: Any) -> dict[str, Any]:
    compact = _compact(_resolve(row.get("answer", {}), ctx))
    gaps = list(row.get("gaps") or [])
    if compact in {"unknown", "[]", "{}"}:
        gaps.append("not enough evidence in ProjectMapReport")
    return {
        "id": row.get("id"),
        "question": row.get("question"),
        "answer": compact,
        "evidence": list(row.get("evidence") or []),
        "confidence": row.get("confidence") or ("low" if gaps else "high"),
        "gaps": gaps,
    }


def _resolve(spec: dict[str, Any], ctx: Any) -> Any:
    provider = str(spec.get("provider") or "")
    if provider == "ctx":
        return _ctx_path(ctx, spec.get("path", []))
    if provider == "constant":
        return spec.get("value")
    if provider == "target":
        return _target(ctx)
    if provider == "helper":
        return _helper(str(spec.get("name") or ""), ctx, list(spec.get("args") or []))
    if provider == "first":
        for item in spec.get("items", []):
            value = _resolve(dict(item), ctx)
            if _compact(value) not in {"unknown", "[]", "{}"}:
                return value
        return None
    if provider == "object":
        return {key: _resolve(dict(value), ctx) for key, value in dict(spec.get("fields") or {}).items()}
    return None


def _ctx_path(ctx: Any, path: Any) -> Any:
    current: Any = ctx
    for part in path if isinstance(path, list) else []:
        if isinstance(current, dict):
            current = current.get(str(part))
        else:
            current = getattr(current, str(part), None)
        if current is None:
            return None
    return current


def _helper(name: str, ctx: Any, args: list[Any]) -> Any:
    function = getattr(answer_helpers, f"_{name}", None)
    if function is None:
        raise ValueError(f"unknown role answer provider: {name}")
    resolved_args = [_target(ctx) if item == "$target" else item for item in args]
    return function(ctx, *resolved_args)


def _target(ctx: Any) -> str:
    return answer_helpers._first_capability(ctx)


def _compact(value: Any) -> str:
    return answer_helpers._compact(value)
