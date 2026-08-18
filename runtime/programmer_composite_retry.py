"""One bounded schema-correction retry for composite L4.5 candidates."""

from __future__ import annotations

import json
from typing import Any, Callable

from .local_inference import LocalInferenceConfig, LocalInferenceError
from .programmer_llm_candidate_contract import candidate_errors


def retry_composite_payload(
    *,
    evidence: dict[str, Any],
    normalized: dict[str, Any],
    initial_payload: dict[str, Any],
    messages: list[dict[str, str]],
    config: LocalInferenceConfig,
    caller: Callable[..., dict[str, Any]],
) -> dict[str, Any] | None:
    changes = [dict(item) for item in list(evidence.get("change_targets") or [])]
    if len(changes) < 2:
        return None
    recipe = dict(normalized.get("patch_recipe_hypothesis") or {})
    errors = candidate_errors(
        recipe,
        str(evidence.get("target") or ""),
        str(evidence.get("source_excerpt") or ""),
        allowed_targets=[str(item.get("target") or "") for item in changes],
        source_excerpts={str(item.get("target") or ""): str(item.get("source_excerpt") or "") for item in changes},
    )
    if normalized.get("action") != "propose_patch_recipe":
        errors.append("composite_recipe_not_proposed")
    if not list(recipe.get("edits") or []):
        errors.append("missing_composite_edits")
    if not errors:
        return None
    correction = (
        "Correct the previous JSON candidate. Rejection errors: "
        + ", ".join(dict.fromkeys(errors))
        + ". Return propose_patch_recipe with replace_functions and one complete edits item per required target. "
        "Each replacement_source must contain exactly one function declaration with its existing signature. "
        "Never include imports, markdown, module constants, or a second function in replacement_source."
    )
    retry_messages = [
        *messages,
        {"role": "assistant", "content": json.dumps(initial_payload, ensure_ascii=False, sort_keys=True)},
        {"role": "user", "content": correction},
    ]
    try:
        return caller(retry_messages, config=config)
    except LocalInferenceError:
        return None
