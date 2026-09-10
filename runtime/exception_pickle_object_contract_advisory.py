from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat

ALLOWED_CONTRACT_KINDS = {
    "attribute_object",
    "mapping_object",
    "iterable_string_list",
    "string_like",
    "exception_like",
    "method_object",
    "opaque_hold",
}


def llm_advisory(
    *,
    row: dict[str, Any],
    source: str,
    contracts: list[dict[str, Any]],
    config: LocalInferenceConfig,
) -> dict[str, Any]:
    try:
        response = call_json_chat(messages(row=row, source=source, contracts=contracts), config=config)
    except LocalInferenceError as exc:
        return {"source": "deterministic_fallback", "llm_invoked": False, "accepted": False, "error": str(exc)}
    suggestions = []
    by_parameter = {item["parameter"]: item for item in contracts}
    for item in response.get("contracts") or []:
        if not isinstance(item, dict):
            continue
        parameter = str(item.get("parameter") or "")
        kind = str(item.get("contract_kind") or "")
        reason = str(item.get("reason") or "")[:240]
        if parameter not in by_parameter or kind not in ALLOWED_CONTRACT_KINDS:
            continue
        if kind == "opaque_hold":
            suggestions.append({"parameter": parameter, "contract_kind": kind, "accepted": True, "reason": reason})
        elif by_parameter[parameter]["contract_kind"] == kind:
            suggestions.append({"parameter": parameter, "contract_kind": kind, "accepted": True, "reason": reason})
        else:
            suggestions.append({
                "parameter": parameter,
                "contract_kind": kind,
                "accepted": False,
                "reason": "LLM suggestion conflicts with deterministic source evidence",
            })
    return {
        "source": config.provider_label,
        "model": config.model,
        "llm_invoked": True,
        "accepted": any(item.get("accepted") for item in suggestions),
        "suggestions": suggestions,
        "authority": "advisory_only",
    }


def messages(*, row: dict[str, Any], source: str, contracts: list[dict[str, Any]]) -> list[dict[str, str]]:
    compact = {
        "project": row.get("canonical_project") or row.get("project"),
        "target": f"{row.get('path')}:{row.get('class_name')}.__init__",
        "required_constructor_parameters": row.get("required_constructor_parameters") or [],
        "deterministic_contracts": contracts,
        "source_excerpt": source[:8000],
    }
    return [
        {
            "role": "system",
            "content": (
                "You are an advisory classifier for exception constructor object samples. "
                "Return JSON only with key contracts. Each contract may use only: "
                "attribute_object, mapping_object, iterable_string_list, string_like, "
                "exception_like, method_object, opaque_hold. Do not propose code changes, KB promotion, "
                "source apply, imports, or execution. Cite only source evidence visible in the excerpt."
            ),
        },
        {"role": "user", "content": json.dumps(compact, ensure_ascii=False, separators=(",", ":"))},
    ]
