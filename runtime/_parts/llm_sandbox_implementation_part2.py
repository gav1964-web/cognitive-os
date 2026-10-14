from __future__ import annotations

import json
import re
import shutil
import subprocess
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.interface_contracts import interface_contract_for_operation
from runtime.local_inference import LocalInferenceError, call_json_chat
from runtime.operation_recipe import recipe_from_operation, validate_operation_recipe
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.sandbox_operation_graph import build_sandbox_operation_graph
from runtime.sandbox_programmer_profiles import expression_policy, load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import sandbox_implementation_policy

def _select_operation_recipe_deterministic(*, prompt: str) -> dict[str, Any] | None:
    lower = prompt.lower()
    numeric_expression = _select_numeric_file_recipe(prompt=prompt, lower=lower)
    if numeric_expression is not None:
        return numeric_expression
    transform = _text_transform_from_prompt(lower)
    if transform is None:
        return None
    contract = _text_interface_contract_from_prompt(lower)
    if contract is None:
        return None
    input_shape = "utf8_text" if contract.startswith("stdin") else "input_path"
    output_shape = "output_path" if "_to_file_" in contract else "utf8_text"
    recipe = {
        "artifact_type": "OperationRecipe",
        "status": "ready",
        "interface_contract": contract,
        "transform": transform,
        "expression": None,
        "input_shape": input_shape,
        "output_shape": output_shape,
        "evidence": [f"deterministic_transform:{transform}", f"deterministic_contract:{contract}"],
        "source": "deterministic_recipe_parser",
    }
    ok, _errors = validate_operation_recipe(recipe)
    return recipe if ok else None

def _select_numeric_file_recipe(*, prompt: str, lower: str) -> dict[str, Any] | None:
    numeric_rules = dict(load_operation_recipe_rules().get("numeric") or {})
    wants_file_output = _has_any_marker(lower, numeric_rules.get("file_output_markers", []))
    has_args = _has_any_marker(lower, numeric_rules.get("argument_markers", []))
    has_math = _has_any_marker(lower, numeric_rules.get("math_markers", []))
    if not (wants_file_output and has_args and has_math):
        return None
    expression = _extract_symbolic_numeric_expression(prompt) or _known_numeric_expression_from_words(lower)
    if expression is None:
        return None
    recipe = {
        "artifact_type": "OperationRecipe",
        "status": "ready",
        "interface_contract": "argv_to_file_numeric_expression",
        "transform": "numeric_expression",
        "expression": expression,
        "input_shape": "numeric_args_plus_output_path",
        "output_shape": "output_path",
        "evidence": [f"deterministic_numeric_expression:{expression}", "deterministic_contract:argv_to_file_numeric_expression"],
        "source": "deterministic_recipe_parser",
    }
    ok, _errors = validate_operation_recipe(recipe)
    return recipe if ok else None

def _text_transform_from_prompt(lower: str) -> str | None:
    for transform, row in dict(load_operation_recipe_rules().get("text_transforms") or {}).items():
        if _has_any_marker(lower, dict(row).get("markers", [])):
            return str(transform)
    return None

def _text_interface_contract_from_prompt(lower: str) -> str | None:
    rules = load_operation_recipe_rules()
    marker_groups = dict(rules.get("text_interface_markers") or {})
    matched = {
        name
        for name, markers in marker_groups.items()
        if _has_any_marker(lower, markers)
    }
    for row in rules.get("text_interface_resolution") or []:
        when = dict(dict(row).get("when") or {})
        if when.get("input") in matched and when.get("output") in matched:
            return str(dict(row).get("interface_contract") or "")
    return None

def _text_expression_for_transform(transform: str) -> str | None:
    row = dict(dict(load_operation_recipe_rules().get("text_transforms") or {}).get(transform) or {})
    return str(row.get("expression") or "") or None

def _has_any_marker(lower: str, markers: Any) -> bool:
    return any(str(marker) in lower for marker in markers or [])

def _expected_for_text_expression(transform: str, sample: str) -> str:
    if transform == "uppercase":
        return sample.upper()
    if transform == "lowercase":
        return sample.lower()
    if transform == "trim":
        return sample.strip() + "\n"
    if transform == "reverse":
        return sample[::-1]
    if transform == "word_count":
        return str(len(sample.split())) + "\n"
    raise ValueError(f"unsupported text transform: {transform}")

def _select_composition(*, root: Path, prompt: str, operations: list[dict[str, Any]]) -> SandboxOperation | None:
    operation_by_id = {str(row.get("id")): row for row in operations}
    for row in _load_compositions(root):
        if not _composition_matches(prompt=prompt, row=row):
            continue
        steps = _composition_steps(row=row, operation_by_id=operation_by_id)
        return SandboxOperation(
            operation=str(row["id"]),
            package=str(row["package"]),
            description=str(row.get("description") or ""),
            evidence=[f"composition:{step['operation']}" for step in steps],
            expression=None,
            profile="operation_composition",
            sample=str(row["sample"]),
            expected=str(row["expected"]),
            steps=steps,
        )
    return None

def _load_compositions(root: Path) -> list[dict[str, Any]]:
    path = root / "registry" / "sandbox_programmer_compositions.json"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "registry" / "sandbox_programmer_compositions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("compositions")
    if not isinstance(rows, list):
        raise ValueError("sandbox_programmer_compositions.json requires compositions list")
    return [dict(row) for row in rows]

def _composition_matches(*, prompt: str, row: dict[str, Any]) -> bool:
    match_all = [str(item).lower() for item in row.get("match_all", [])]
    if any(not marker_matches(prompt, marker) for marker in match_all):
        return False
    groups = row.get("match_any_groups", [])
    if not isinstance(groups, list):
        raise ValueError("composition match_any_groups must be a list")
    for group in groups:
        markers = [str(item).lower() for item in group]
        if not markers or not any(marker_matches(prompt, marker) for marker in markers):
            return False
    return True

def _composition_steps(*, row: dict[str, Any], operation_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    raw_steps = row.get("steps")
    if not isinstance(raw_steps, list) or not 2 <= len(raw_steps) <= 3:
        raise ValueError("composition steps must contain 2-3 steps")
    steps = []
    for raw_step in raw_steps:
        step = dict(raw_step)
        operation_id = str(step.get("operation") or "")
        operation_row = operation_by_id.get(operation_id)
        if operation_row is None:
            raise ValueError(f"composition references unknown operation: {operation_id}")
        profile = str(operation_row.get("profile") or "text_expression")
        _validate_operation(
            expression=str(operation_row["expression"]) if operation_row.get("expression") is not None else None,
            profile=profile,
        )
        steps.append({"operation": operation_id, "profile": profile})
    return steps

def _propose_operation_with_l45(*, prompt: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    compact_operations = [
        {
            "id": str(row.get("id")),
            "description": str(row.get("description") or ""),
            "profile": str(row.get("profile") or "text_expression"),
            "match": [str(item) for item in row.get("match", [])],
        }
        for row in operations
    ]
    base = {
        "status": "blocked_model_no_match",
        "strategy": "l45_registry_operation_normalization",
        "model_invoked": True,
        "candidate_operation_id": None,
        "confidence": 0.0,
        "evidence": [],
        "errors": [],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You normalize a user request to one existing sandbox operation. "
                "Return JSON only. You may not invent operations, code, libraries, files, or commands. "
                "Schema: {\"operation_id\": string|null, \"confidence\": number, \"reason\": string}. "
                "Use null if no listed operation fits."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "prompt": prompt,
                    "available_operations": compact_operations,
                    "selection_rule": "choose only an id from available_operations when it clearly satisfies the prompt",
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        proposal = call_json_chat(messages)
    except LocalInferenceError as exc:
        base["status"] = "blocked_model_error"
        base["errors"].append(str(exc))
        return base
    operation_id = proposal.get("operation_id")
    confidence = _float_or_zero(proposal.get("confidence"))
    valid_ids = {str(row.get("id")) for row in operations}
    base["raw_model_proposal"] = {
        "operation_id": operation_id if operation_id is None else str(operation_id),
        "confidence": confidence,
        "reason": str(proposal.get("reason") or ""),
    }
    if operation_id is None:
        return base
    operation_id = str(operation_id)
    if operation_id not in valid_ids:
        base["status"] = "blocked_invalid_model_operation"
        base["candidate_operation_id"] = operation_id
        base["errors"].append("operation_id is not present in registry")
        return base
    if confidence < 0.55:
        base["status"] = "blocked_low_model_confidence"
        base["candidate_operation_id"] = operation_id
        base["confidence"] = confidence
        return base
    base.update(
        {
            "status": "resolved",
            "candidate_operation_id": operation_id,
            "confidence": confidence,
            "evidence": [f"model_reason:{base['raw_model_proposal']['reason']}"],
        }
    )
    return base

def _propose_operation_recipe_with_l45(*, prompt: str) -> dict[str, Any]:
    recipe_rules = load_operation_recipe_rules()
    prompt_rules = dict(recipe_rules.get("l45_prompt") or {})
    allowed_contracts = ", ".join(str(item) for item in recipe_rules.get("allowed_interface_contracts", []))
    allowed = ", ".join(str(item) for item in recipe_rules.get("allowed_transforms", []))
    base: dict[str, Any] = {
        "status": "blocked_model_no_recipe",
        "strategy": "l45_operation_recipe_parser",
        "model_invoked": True,
        "candidate_operation_id": None,
        "evidence": [],
        "errors": [],
    }
    messages = [
        {
            "role": "system",
            "content": (
                f"{prompt_rules.get('system_prefix')} "
                f"Schema: {prompt_rules.get('schema')}. "
                f"Allowed interface_contract: {allowed_contracts}. "
                f"Allowed transform: {allowed}. "
                f"{prompt_rules.get('numeric_expression_rule')} "
                f"{prompt_rules.get('text_transform_rule')}"
            ),
        },
        {"role": "user", "content": json.dumps({"prompt": prompt}, ensure_ascii=False)},
    ]
    try:
        proposal = call_json_chat(messages)
    except LocalInferenceError as exc:
        base["status"] = "blocked_model_error"
        base["errors"].append(str(exc))
        return base
    recipe = {
        "artifact_type": "OperationRecipe",
        "status": "ready",
        "interface_contract": str(proposal.get("interface_contract") or ""),
        "transform": str(proposal.get("transform") or ""),
        "expression": proposal.get("expression"),
        "input_shape": str(proposal.get("input_shape") or ""),
        "output_shape": str(proposal.get("output_shape") or ""),
        "evidence": [str(item) for item in proposal.get("evidence", [])] if isinstance(proposal.get("evidence"), list) else [],
        "source": "l45",
    }
    ok, errors = validate_operation_recipe(recipe)
    if not ok:
        base["status"] = "blocked_invalid_operation_recipe"
        base["operation_recipe"] = recipe
        base["errors"].extend(errors)
        return base
    base.update(
        {
            "status": "resolved",
            "candidate_operation_id": f"recipe:{recipe['interface_contract']}:{recipe['transform']}",
            "operation_recipe": recipe,
            "evidence": [*recipe["evidence"], "l45_operation_recipe_parser"],
        }
    )
    return base

def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def _load_operations(root: Path) -> list[dict[str, Any]]:
    path = root / "registry" / "sandbox_programmer_operations.json"
    if not path.is_file():
        path = Path(__file__).resolve().parents[2] / "registry" / "sandbox_programmer_operations.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("operations")
    if not isinstance(rows, list):
        raise ValueError("sandbox_programmer_operations.json requires operations list")
    return [dict(row) for row in rows]
