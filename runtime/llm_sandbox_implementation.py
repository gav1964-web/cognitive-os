"""Bounded sandbox implementation path for prompts not covered by templates."""

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

from .interface_contracts import interface_contract_for_operation
from .local_inference import LocalInferenceError, call_json_chat
from .operation_recipe import recipe_from_operation, validate_operation_recipe
from .operation_recipe_rules import load_operation_recipe_rules
from .sandbox_operation_graph import build_sandbox_operation_graph
from .sandbox_programmer_profiles import expression_policy, load_sandbox_programmer_profiles
from .sandbox_release_policy import sandbox_implementation_policy


@dataclass(frozen=True)
class SandboxOperation:
    operation: str
    package: str
    description: str
    evidence: list[str]
    expression: str | None
    profile: str
    sample: str
    expected: str
    steps: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_llm_sandbox_implementation(
    *,
    root: Path,
    prompt: str,
    write: bool = False,
    output_dir: Path | None = None,
    use_model: bool = False,
) -> dict[str, Any]:
    """Create and verify a tiny generated package in isolation.

    The current implementation is intentionally conservative: LLM may be enabled
    later as a hypothesis source, but executable code is generated only from an
    allowlisted operation contract.
    """

    operation, route_resolution = _select_operation(root=root, prompt=prompt, use_model=use_model)
    if operation is None:
        result_policy = sandbox_implementation_policy()
        return {
            "artifact_type": "LLMSandboxImplementationResult",
            "status": "blocked",
            "reason": "prompt did not map to a bounded allowlisted sandbox operation",
            "prompt": prompt,
            "route_resolution": route_resolution,
            "llm_policy": _llm_policy(use_model=use_model),
            "promotion_allowed": result_policy.get("promotion_allowed", False),
            "source_code_changes": result_policy.get("source_code_changes", False),
            "registry_changes": result_policy.get("registry_changes", False),
        }
    project_dir = output_dir or _default_output_dir(root, operation.operation)
    if write:
        _write_project(project_dir, operation, prompt)
        compile_result = _run([_python(), "-m", "compileall", "-q", "."], cwd=project_dir)
        test_result = _run([_python(), "-m", "pytest", "tests", "-q"], cwd=project_dir)
    else:
        compile_result = {"status": "not_run", "command": "python -m compileall -q ."}
        test_result = {"status": "not_run", "command": "python -m pytest tests -q"}
    passed = compile_result["status"] in {"passed", "not_run"} and test_result["status"] in {"passed", "not_run"}
    interface_contract = interface_contract_for_operation(root, operation.to_dict())
    operation_recipe = recipe_from_operation(operation.to_dict(), interface_contract=interface_contract)
    result_policy = sandbox_implementation_policy()
    return {
        "artifact_type": "LLMSandboxImplementationResult",
        "status": "sandbox_verified" if passed and write else "planned",
        "prompt": prompt,
        "route_resolution": route_resolution,
        "implementation_plan": {
            "artifact_type": "SandboxImplementationPlan",
            "status": "ready",
            "operation": operation.to_dict(),
            "operation_recipe": operation_recipe,
            "interface_contract": interface_contract,
            "operation_graph": build_sandbox_operation_graph(operation.to_dict()),
            "allowed_side_effects": list(result_policy.get("allowed_side_effects", [])),
            "forbidden_side_effects": list(result_policy.get("forbidden_side_effects", [])),
        },
        "project_dir": project_dir.as_posix(),
        "files": [
            "pyproject.toml",
            "README.md",
            f"src/{operation.package}/__init__.py",
            f"src/{operation.package}/cli.py",
            "tests/fixtures/input.txt",
            "tests/fixtures/expected.txt",
            "tests/test_cli.py",
        ],
        "verification": {
            "status": "passed" if passed and write else "not_run",
            "compile": compile_result,
            "tests": test_result,
        },
        "llm_policy": _llm_policy(use_model=use_model),
        "promotion_allowed": result_policy.get("promotion_allowed", False),
        "source_code_changes": result_policy.get("source_code_changes", False),
        "registry_changes": result_policy.get("registry_changes", False),
        "next_action": str(result_policy.get("next_action") or "review_then_consider_kb_candidate_after_repeated_confirmed_cases"),
    }


def _select_operation(*, root: Path, prompt: str, use_model: bool = False) -> tuple[SandboxOperation | None, dict[str, Any]]:
    lower = prompt.lower()
    operations = _load_operations(root)
    resolution: dict[str, Any] = {
        "artifact_type": "SandboxProgrammerRouteResolution",
        "status": "unresolved",
        "strategy": "deterministic_registry_match",
        "model_invoked": False,
        "candidate_operation_id": None,
        "evidence": [],
        "errors": [],
    }
    if not any(marker in lower for marker in ("cli", "утил", ".py", "script", "скрипт", "консоль", "инструмент", "программ")):
        resolution["status"] = "blocked_not_cli_request"
        return None, resolution
    composition = _select_composition(root=root, prompt=lower, operations=operations)
    if composition is not None:
        resolution.update(
            {
                "status": "resolved",
                "strategy": "deterministic_operation_composition",
                "candidate_operation_id": composition.operation,
                "evidence": composition.evidence,
            }
        )
        return composition, resolution
    numeric_expression = _select_numeric_expression_from_prompt(prompt)
    if numeric_expression is not None:
        resolution.update(
            {
                "status": "resolved",
                "strategy": "deterministic_numeric_expression_extraction",
                "candidate_operation_id": numeric_expression.operation,
                "evidence": numeric_expression.evidence,
            }
        )
        return numeric_expression, resolution
    interface_operation = _select_interface_specific_operation(prompt=lower, operations=operations)
    if interface_operation is not None:
        resolution.update(
            {
                "status": "resolved",
                "strategy": "deterministic_interface_specific_registry_match",
                "candidate_operation_id": interface_operation.operation,
                "evidence": interface_operation.evidence,
            }
        )
        return interface_operation, resolution
    deterministic_recipe = _select_operation_recipe_deterministic(prompt=prompt)
    if deterministic_recipe is not None:
        operation = _operation_from_recipe(deterministic_recipe)
        if operation is not None:
            resolution.update(
                {
                    "status": "resolved",
                    "strategy": "deterministic_operation_recipe_parser",
                    "candidate_operation_id": operation.operation,
                    "evidence": operation.evidence,
                }
            )
            return operation, resolution
    for row in operations:
        markers = [str(item).lower() for item in row.get("match", [])]
        if any(marker in lower for marker in markers):
            evidence = [marker for marker in markers if marker in lower]
            resolution.update(
                {
                    "status": "resolved",
                    "strategy": "deterministic_registry_match",
                    "candidate_operation_id": str(row["id"]),
                    "evidence": evidence,
                }
            )
            return _operation_from_row(row, evidence=evidence), resolution
    if not use_model:
        resolution["status"] = "blocked_no_deterministic_match"
        return None, resolution
    proposal = _propose_operation_with_l45(prompt=prompt, operations=operations)
    resolution.update(proposal)
    operation_id = proposal.get("candidate_operation_id")
    if proposal.get("status") == "resolved" and operation_id:
        for row in operations:
            if str(row.get("id")) == str(operation_id):
                return _operation_from_row(row, evidence=[f"l45:{operation_id}"]), resolution
        resolution["status"] = "blocked_invalid_model_operation"
        resolution["errors"].append("model proposed operation_id not present in registry")
        return None, resolution
    if proposal.get("status") != "blocked_model_no_match":
        return None, resolution
    recipe_proposal = _propose_operation_recipe_with_l45(prompt=prompt)
    if recipe_proposal.get("status") == "resolved":
        operation = _operation_from_recipe(recipe_proposal["operation_recipe"])
        if operation is not None:
            resolution.update(recipe_proposal)
            return operation, resolution
    resolution.update(recipe_proposal)
    return None, resolution


def _operation_from_row(row: dict[str, Any], *, evidence: list[str]) -> SandboxOperation:
    expression = str(row["expression"]) if row.get("expression") is not None else None
    profile = str(row.get("profile") or "text_expression")
    _validate_operation(expression=expression, profile=profile)
    return SandboxOperation(
        operation=str(row["id"]),
        package=str(row["package"]),
        description=str(row.get("description") or ""),
        evidence=evidence,
        expression=expression,
        profile=profile,
        sample=str(row["sample"]),
        expected=str(row["expected"]),
        steps=None,
    )


def _select_interface_specific_operation(*, prompt: str, operations: list[dict[str, Any]]) -> SandboxOperation | None:
    preferred_profiles: list[str] = []
    wants_file_output = any(marker in prompt for marker in ("в файл", "output file", "сохран", "запис"))
    if ("stdin" in prompt or "стандартный ввод" in prompt) and not wants_file_output:
        preferred_profiles.append("stdin_text_expression")
    if "stdout" in prompt and any(marker in prompt for marker in ("файл", "file")):
        preferred_profiles.append("file_stdout_text_expression")
    if not preferred_profiles:
        return None
    for profile in preferred_profiles:
        for row in operations:
            if str(row.get("profile") or "") != profile:
                continue
            markers = [str(item).lower() for item in row.get("match", [])]
            if any(marker in prompt for marker in markers):
                evidence = [marker for marker in markers if marker in prompt]
                return _operation_from_row(row, evidence=evidence)
    return None


def _select_numeric_expression_from_prompt(prompt: str) -> SandboxOperation | None:
    lower = prompt.lower()
    if not _looks_like_numeric_argv_stdout_prompt(lower):
        return None
    expression = _extract_symbolic_numeric_expression(prompt)
    sample_values = _sample_values_for_expression(prompt=prompt, expression=expression)
    if expression is None:
        expression = _known_numeric_expression_from_words(lower)
    if expression is None:
        return None
    _validate_numeric_args_expression(expression)
    arg_count = max(_expression_arg_count(expression), len(sample_values))
    if not 1 <= arg_count <= 5:
        return None
    sample_values = (sample_values + _default_numeric_args(arg_count))[:arg_count]
    expected_value = _evaluate_numeric_expression(expression, sample_values)
    expected = _format_numeric_value(expected_value) + "\n"
    normalized = re.sub(r"[^a-z0-9]+", "_", expression.lower()).strip("_") or "expression"
    return SandboxOperation(
        operation=f"numeric_args_expression_{normalized}",
        package=f"numeric_expr_{normalized}_cli"[:60].rstrip("_"),
        description="Accept numeric command-line arguments, compute a validated arithmetic expression, and print stdout.",
        evidence=[f"expression:{expression}", f"args:{arg_count}"],
        expression=expression,
        profile="numeric_args_expression",
        sample=" ".join(_format_numeric_value(value) for value in sample_values),
        expected=expected,
        steps=None,
    )


def _operation_from_recipe(recipe: dict[str, Any]) -> SandboxOperation | None:
    ok, errors = validate_operation_recipe(recipe)
    if not ok:
        return None
    contract = str(recipe.get("interface_contract") or "")
    transform = str(recipe.get("transform") or "")
    expression = str(recipe.get("expression") or "") if recipe.get("expression") is not None else None
    if transform == "numeric_expression":
        if contract not in {"argv_stdout_numeric_expression", "argv_to_file_numeric_expression"} or expression is None:
            return None
        _validate_numeric_args_expression(expression)
        arg_count = max(1, _expression_arg_count(expression))
        sample_values = _default_numeric_args(arg_count)
        expected = _format_numeric_value(_evaluate_numeric_expression(expression, sample_values)) + "\n"
        normalized = re.sub(r"[^a-z0-9]+", "_", expression.lower()).strip("_") or "expression"
        return SandboxOperation(
            operation=f"recipe_numeric_args_expression_{normalized}",
            package=f"recipe_numeric_expr_{normalized}_cli"[:60].rstrip("_"),
            description="OperationRecipe numeric argv expression CLI.",
            evidence=[*list(recipe.get("evidence") or []), "l45_operation_recipe"],
            expression=expression,
            profile="numeric_args_file_expression" if contract == "argv_to_file_numeric_expression" else "numeric_args_expression",
            sample=" ".join(_format_numeric_value(value) for value in sample_values),
            expected=expected,
            steps=None,
        )
    text_expression = _text_expression_for_transform(transform)
    if text_expression is None:
        return None
    sample = "One two\nthree\n"
    expected = _expected_for_text_expression(transform, sample)
    profile = str(dict(load_operation_recipe_rules().get("contract_profiles") or {}).get(contract) or "")
    if profile is None:
        return None
    if not profile:
        return None
    return SandboxOperation(
        operation=f"recipe_{contract}_{transform}",
        package=f"recipe_{contract}_{transform}_cli"[:60].rstrip("_"),
        description=f"OperationRecipe {contract} {transform}.",
        evidence=[*list(recipe.get("evidence") or []), "l45_operation_recipe"],
        expression=text_expression,
        profile=profile,
        sample=sample,
        expected=expected,
        steps=None,
    )


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
        path = Path(__file__).resolve().parents[1] / "registry" / "sandbox_programmer_compositions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("compositions")
    if not isinstance(rows, list):
        raise ValueError("sandbox_programmer_compositions.json requires compositions list")
    return [dict(row) for row in rows]


def _composition_matches(*, prompt: str, row: dict[str, Any]) -> bool:
    match_all = [str(item).lower() for item in row.get("match_all", [])]
    if any(marker not in prompt for marker in match_all):
        return False
    groups = row.get("match_any_groups", [])
    if not isinstance(groups, list):
        raise ValueError("composition match_any_groups must be a list")
    for group in groups:
        markers = [str(item).lower() for item in group]
        if not markers or not any(marker in prompt for marker in markers):
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
        path = Path(__file__).resolve().parents[1] / "registry" / "sandbox_programmer_operations.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("operations")
    if not isinstance(rows, list):
        raise ValueError("sandbox_programmer_operations.json requires operations list")
    return [dict(row) for row in rows]


def _validate_operation(*, expression: str | None, profile: str) -> None:
    try:
        policy = expression_policy(profile)
    except Exception as exc:
        raise ValueError(f"unsupported sandbox operation profile: {profile}") from exc
    if policy == "no_expression":
        if expression is not None:
            raise ValueError(f"{profile} operation must not provide expression")
        return
    if policy == "text_expression_required":
        if expression is None:
            raise ValueError(f"{profile} operation requires expression")
        _validate_expression(expression)
    elif policy == "numeric_expression_required":
        if expression is None:
            raise ValueError(f"{profile} operation requires expression")
        _validate_numeric_args_expression(expression)
    else:
        raise ValueError(f"unsupported expression policy for profile {profile}: {policy}")


def _validate_expression(expression: str) -> None:
    tree = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.Add,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Attribute,
        ast.Constant,
        ast.Subscript,
        ast.Slice,
        ast.UnaryOp,
        ast.USub,
    )
    policy = dict(load_sandbox_programmer_profiles().get("text_expression_policy") or {})
    allowed_names = {str(item) for item in policy.get("allowed_names", [])}
    allowed_methods = {str(item) for item in policy.get("allowed_methods", [])}
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"unsupported sandbox operation expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"unsupported sandbox operation expression name: {node.id}")
        if isinstance(node, ast.Attribute):
            if not _is_allowed_attribute(node=node, allowed_methods=allowed_methods):
                raise ValueError(f"unsupported sandbox operation expression attribute: {node.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"str", "len"}:
                continue
            if isinstance(func, ast.Attribute) and _is_allowed_attribute(node=func, allowed_methods=allowed_methods):
                continue
            raise ValueError("unsupported sandbox operation expression call")


def _is_allowed_attribute(*, node: ast.Attribute, allowed_methods: set[str]) -> bool:
    if node.attr not in allowed_methods:
        return False
    if isinstance(node.value, ast.Name) and node.value.id == "text":
        return True
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.attr == "join":
        return True
    return False


def _validate_numeric_args_expression(expression: str) -> None:
    tree = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.UnaryOp,
        ast.USub,
    )
    policy = dict(load_sandbox_programmer_profiles().get("numeric_expression_policy") or {})
    allowed_names = {str(item) for item in policy.get("allowed_names", [])}
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"unsupported numeric args expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"unsupported numeric args expression name: {node.id}")


def _looks_like_numeric_argv_stdout_prompt(lower: str) -> bool:
    has_cli = any(marker in lower for marker in ("cli", "программ", "program", "script", "скрипт"))
    has_args = any(marker in lower for marker in ("аргумент", "параметр", "argument", "parameter", "argv"))
    has_output = any(marker in lower for marker in ("вывод", "stdout", "терминал", "консоль", "print", "напечат"))
    has_math = any(marker in lower for marker in ("+", "-", "*", "/", "слож", "выч", "умнож", "перемнож", "дели", "делит"))
    return has_cli and has_args and has_output and has_math


def _extract_symbolic_numeric_expression(prompt: str) -> str | None:
    cleaned = prompt.replace("×", "*").replace("÷", "/").replace(",", " ")
    candidates = re.findall(r"(?<![A-Za-zА-Яа-я])(?:[abcdeABCDE0-9(][abcdeABCDE0-9\s()+\-*/.]*[+\-*/][abcdeABCDE0-9\s()+\-*/.]*)", cleaned)
    for candidate in candidates:
        expression = _normalize_expression_candidate(candidate)
        if expression is None:
            continue
        if _expression_arg_count(expression) > 0:
            return expression
    return None


def _normalize_expression_candidate(candidate: str) -> str | None:
    raw = candidate.strip().lower()
    if not raw:
        return None
    if not re.fullmatch(r"[abcde0-9\s()+\-*/.]+", raw):
        return None
    raw = re.sub(r"\s+", "", raw)
    raw = _replace_numeric_literals_with_arg_names(raw)
    try:
        _validate_numeric_args_expression(raw)
    except (SyntaxError, ValueError):
        return None
    return raw


def _replace_numeric_literals_with_arg_names(expression: str) -> str:
    names = iter(["a", "b", "c", "d", "e"])

    def repl(match: re.Match[str]) -> str:
        return next(names, match.group(0))

    if re.search(r"[abcde]", expression):
        return expression
    return re.sub(r"(?<![A-Za-z])\d+(?:\.\d+)?", repl, expression)


def _known_numeric_expression_from_words(lower: str) -> str | None:
    if (
        any(marker in lower for marker in ("первые два", "first two"))
        and any(marker in lower for marker in ("перемнож", "умнож", "multiply"))
        and any(marker in lower for marker in ("треть", "third"))
        and any(marker in lower for marker in ("склады", "прибав", "add"))
    ):
        return "a*b+c"
    if any(marker in lower for marker in ("слож", "sum", "add")) and any(marker in lower for marker in ("два", "two", "2 ")):
        return "a+b"
    return None


def _sample_values_for_expression(*, prompt: str, expression: str | None) -> list[float]:
    example_match = re.search(r"(?:например|example|e\.g\.)\s*([0-9][0-9\s()+\-*/.]*[+\-*/][0-9\s()+\-*/.]*)", prompt, flags=re.IGNORECASE)
    if example_match:
        values = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", example_match.group(1))]
        if values:
            return values
    arg_count = _expression_arg_count(expression or "")
    return _default_numeric_args(arg_count)


def _default_numeric_args(arg_count: int) -> list[float]:
    defaults = [2.0, 3.0, 4.0, 5.0, 6.0]
    return defaults[: max(1, min(arg_count, len(defaults)))]


def _expression_arg_count(expression: str) -> int:
    names = {name for name in re.findall(r"\b[abcde]\b", expression)}
    if not names:
        return 0
    order = ["a", "b", "c", "d", "e"]
    return max(order.index(name) + 1 for name in names)


def _evaluate_numeric_expression(expression: str, values: list[float]) -> int | float:
    _validate_numeric_args_expression(expression)
    names = ["a", "b", "c", "d", "e"]
    env = {name: values[index] for index, name in enumerate(names[: len(values)])}
    tree = ast.parse(expression, mode="eval")
    return _eval_numeric_node(tree.body, env)


def _eval_numeric_node(node: ast.AST, env: dict[str, float]) -> int | float:
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_numeric_node(node.operand, env)
    if isinstance(node, ast.BinOp):
        left = _eval_numeric_node(node.left, env)
        right = _eval_numeric_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f"unsupported numeric expression node: {type(node).__name__}")


def _format_numeric_value(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _write_project(project_dir: Path, operation: SandboxOperation, prompt: str) -> None:
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    package_dir = project_dir / "src" / operation.package
    tests_dir = project_dir / "tests"
    fixtures_dir = tests_dir / "fixtures"
    package_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "pyproject.toml").write_text(_pyproject(operation), encoding="utf-8")
    (project_dir / "README.md").write_text(_readme(operation, prompt), encoding="utf-8")
    (package_dir / "__init__.py").write_text('"""Generated sandbox CLI package."""\n', encoding="utf-8")
    (package_dir / "cli.py").write_text(_cli_py(operation), encoding="utf-8")
    (fixtures_dir / "input.txt").write_text(operation.sample, encoding="utf-8")
    (fixtures_dir / "expected.txt").write_text(operation.expected, encoding="utf-8")
    (tests_dir / "test_cli.py").write_text(_test_py(operation), encoding="utf-8")


def _pyproject(operation: SandboxOperation) -> str:
    return f"""[project]
name = "{operation.package}"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["src"]
"""


def _readme(operation: SandboxOperation, prompt: str) -> str:
    if operation.profile in {"numeric_args_sum", "numeric_args_expression"}:
        run_command = f"PYTHONPATH=src python -m {operation.package}.cli {operation.sample}"
    elif operation.profile == "numeric_args_file_expression":
        run_command = f"PYTHONPATH=src python -m {operation.package}.cli {operation.sample} output.txt"
    elif operation.profile == "stdin_text_expression":
        run_command = f"echo sample | PYTHONPATH=src python -m {operation.package}.cli"
    elif operation.profile == "stdin_file_text_expression":
        run_command = f"echo sample | PYTHONPATH=src python -m {operation.package}.cli output.txt"
    elif operation.profile == "file_stdout_text_expression":
        run_command = f"PYTHONPATH=src python -m {operation.package}.cli input.txt"
    else:
        run_command = f"PYTHONPATH=src python -m {operation.package}.cli input.txt output.txt"
    return f"""# {operation.package}

Generated isolated sandbox package.

Prompt:

```text
{prompt}
```

Run:

```bash
{run_command}
python -m pytest tests -q
```

This package is not merged into source or KB automatically.
"""


def _cli_py(operation: SandboxOperation) -> str:
    if operation.profile == "numeric_args_sum":
        return _numeric_args_cli_py()
    if operation.profile == "numeric_args_expression":
        return _numeric_args_expression_cli_py(operation)
    if operation.profile == "numeric_args_file_expression":
        return _numeric_args_file_expression_cli_py(operation)
    if operation.profile == "stdin_text_expression":
        return _stdin_stdout_cli_py(operation)
    if operation.profile == "stdin_file_text_expression":
        return _stdin_file_cli_py(operation)
    if operation.profile == "file_stdout_text_expression":
        return _file_stdout_cli_py(operation)
    body = _transform_body(operation)
    return f'''from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        if tag == "tr" and self._row is not None:
            if any(cell for cell in self._row):
                self.rows.append(self._row)
            self._row = None


def transform(text: str) -> str:
{body}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    source = Path(args.input)
    if not source.is_file():
        parser.error(f"input file does not exist: {{source}}")
    Path(args.output).write_text(transform(source.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _transform_body(operation: SandboxOperation) -> str:
    if operation.profile == "operation_composition":
        return _composition_transform_body(operation)
    if operation.profile == "text_expression":
        return f"    return {operation.expression}"
    if operation.profile == "line_sort":
        return '''    lines = text.splitlines()
    return "\\n".join(sorted(lines)) + ("\\n" if lines else "")'''
    if operation.profile == "line_unique":
        return '''    seen = set()
    result = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return "\\n".join(result) + ("\\n" if result else "")'''
    if operation.profile == "csv_row_count":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "0\\n"
    data_rows = rows[1:] if rows and any(cell.strip() for cell in rows[0]) else rows
    return str(len([row for row in data_rows if any(cell.strip() for cell in row)])) + "\\n"'''
    if operation.profile == "csv_sort_first_column":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    header, data = rows[0], rows[1:]
    data = sorted(data, key=lambda row: row[0] if row else "")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(header)
    writer.writerows(data)
    return out.getvalue()'''
    if operation.profile == "csv_select_first_two_columns":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    for row in rows:
        writer.writerow(row[:2])
    return out.getvalue()'''
    if operation.profile == "csv_filter_first_column_nonempty":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    header, data = rows[0], rows[1:]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(header)
    writer.writerows([row for row in data if row and row[0].strip()])
    return out.getvalue()'''
    if operation.profile == "csv_sum_second_column":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    total = 0.0
    for row in rows[1:]:
        if len(row) > 1 and row[1].strip():
            total += float(row[1])
    if total.is_integer():
        return str(int(total)) + "\\n"
    return str(total) + "\\n"'''
    if operation.profile == "csv_to_json_records":
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "[]\\n"
    header, data = rows[0], rows[1:]
    records = [dict(zip(header, row)) for row in data]
    return json.dumps(records, ensure_ascii=False, sort_keys=True) + "\\n"'''
    if operation.profile == "html_table_to_csv":
        return '''    parser = _TableParser()
    parser.feed(text)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerows(parser.rows)
    return out.getvalue()'''
    if operation.profile == "json_extract_first_key":
        return '''    payload = json.loads(text)
    if not isinstance(payload, dict) or not payload:
        return "\\n"
    key = sorted(payload)[0]
    return json.dumps(payload[key], ensure_ascii=False, sort_keys=True) + "\\n"'''
    if operation.profile == "json_keys":
        return '''    payload = json.loads(text)
    if not isinstance(payload, dict):
        return "[]\\n"
    return json.dumps(sorted(payload), ensure_ascii=False) + "\\n"'''
    if operation.profile == "json_pretty":
        return '''    payload = json.loads(text)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\\n"'''
    raise ValueError(f"unsupported operation profile: {operation.profile}")


def _composition_transform_body(operation: SandboxOperation) -> str:
    step_ids = [step.get("operation") for step in operation.steps or []]
    if step_ids == ["csv_filter_first_column_nonempty", "csv_select_first_two_columns", "csv_to_json_records"]:
        return '''    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "[]\\n"
    header, data = rows[0], rows[1:]
    filtered = [row for row in data if row and row[0].strip()]
    selected_header = header[:2]
    selected_rows = [row[:2] for row in filtered]
    records = [dict(zip(selected_header, row)) for row in selected_rows]
    return json.dumps(records, ensure_ascii=False, sort_keys=True) + "\\n"'''
    if step_ids == ["trim", "upper"]:
        return '''    return text.strip().upper() + "\\n"'''
    raise ValueError(f"unsupported operation composition: {step_ids}")


def _test_py(operation: SandboxOperation) -> str:
    if operation.profile == "numeric_args_sum":
        return _numeric_args_test_py(operation)
    if operation.profile == "numeric_args_expression":
        return _numeric_args_expression_test_py(operation)
    if operation.profile == "numeric_args_file_expression":
        return _numeric_args_file_expression_test_py(operation)
    if operation.profile == "stdin_text_expression":
        return _stdin_stdout_test_py(operation)
    if operation.profile == "stdin_file_text_expression":
        return _stdin_file_test_py(operation)
    if operation.profile == "file_stdout_text_expression":
        return _file_stdout_test_py(operation)
    return f'''from pathlib import Path
import pytest

from {operation.package}.cli import main, transform


def test_transform_contract():
    assert transform({operation.sample!r}) == {operation.expected!r}


def test_cli_writes_output(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "input.txt"
    expected = (Path(__file__).parent / "fixtures" / "expected.txt").read_text(encoding="utf-8")
    target = tmp_path / "out.txt"
    assert main([str(source), str(target)]) == 0
    assert target.read_text(encoding="utf-8") == expected


def test_cli_rejects_missing_input(tmp_path: Path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing.txt"), str(tmp_path / "out.txt")])
'''


def _numeric_args_cli_py() -> str:
    return '''from __future__ import annotations

import argparse


def parse_number(value: str) -> int | float:
    try:
        return int(value)
    except ValueError:
        return float(value)


def format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def compute_sum(first: str, second: str) -> str:
    return format_number(parse_number(first) + parse_number(second)) + "\\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first")
    parser.add_argument("second")
    args = parser.parse_args(argv)
    try:
        print(compute_sum(args.first, args.second), end="")
    except ValueError as exc:
        parser.error(f"arguments must be numbers: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _numeric_args_test_py(operation: SandboxOperation) -> str:
    first, second = operation.sample.split()
    return f'''import pytest

from {operation.package}.cli import compute_sum, main


def test_compute_sum_contract():
    assert compute_sum({first!r}, {second!r}) == {operation.expected!r}


def test_main_prints_sum(capsys):
    assert main([{first!r}, {second!r}]) == 0
    assert capsys.readouterr().out == {operation.expected!r}


def test_main_rejects_non_numeric_argument():
    with pytest.raises(SystemExit):
        main(["one", "2"])
'''


def _numeric_args_expression_cli_py(operation: SandboxOperation) -> str:
    arg_names = _numeric_arg_names(operation)
    parser_args = "\n".join(f'    parser.add_argument("{name}")' for name in arg_names)
    call_args = ", ".join(f"args.{name}" for name in arg_names)
    parsed_args = "\n".join(f"    {name} = parse_number({name}_raw)" for name in arg_names)
    expression = operation.expression or "0"
    return f'''from __future__ import annotations

import argparse


def parse_number(value: str) -> int | float:
    try:
        return int(value)
    except ValueError:
        return float(value)


def format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def compute_result({", ".join(name + "_raw: str" for name in arg_names)}) -> str:
{parsed_args}
    result = {expression}
    return format_number(result) + "\\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
{parser_args}
    args = parser.parse_args(argv)
    try:
        print(compute_result({call_args}), end="")
    except ValueError as exc:
        parser.error(f"arguments must be numbers: {{exc}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _numeric_args_expression_test_py(operation: SandboxOperation) -> str:
    args = operation.sample.split()
    args_literal = ", ".join(repr(item) for item in args)
    bad_args = ["bad", *args[1:]]
    bad_args_literal = ", ".join(repr(item) for item in bad_args)
    return f'''import pytest

from {operation.package}.cli import compute_result, main


def test_compute_result_contract():
    assert compute_result({args_literal}) == {operation.expected!r}


def test_main_prints_result(capsys):
    assert main([{args_literal}]) == 0
    assert capsys.readouterr().out == {operation.expected!r}


def test_main_rejects_non_numeric_argument():
    with pytest.raises(SystemExit):
        main([{bad_args_literal}])
'''


def _numeric_args_file_expression_cli_py(operation: SandboxOperation) -> str:
    arg_names = _numeric_arg_names(operation)
    parser_args = "\n".join(f'    parser.add_argument("{name}")' for name in arg_names)
    call_args = ", ".join(f"args.{name}" for name in arg_names)
    parsed_args = "\n".join(f"    {name} = parse_number({name}_raw)" for name in arg_names)
    expression = operation.expression or "0"
    return f'''from __future__ import annotations

import argparse
from pathlib import Path


def parse_number(value: str) -> int | float:
    try:
        return int(value)
    except ValueError:
        return float(value)


def format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def compute_result({", ".join(name + "_raw: str" for name in arg_names)}) -> str:
{parsed_args}
    result = {expression}
    return format_number(result) + "\\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
{parser_args}
    parser.add_argument("output")
    args = parser.parse_args(argv)
    try:
        Path(args.output).write_text(compute_result({call_args}), encoding="utf-8")
    except ValueError as exc:
        parser.error(f"arguments must be numbers: {{exc}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _numeric_args_file_expression_test_py(operation: SandboxOperation) -> str:
    args = operation.sample.split()
    args_literal = ", ".join(repr(item) for item in args)
    bad_args = ["bad", *args[1:], "out.txt"]
    bad_args_literal = ", ".join(repr(item) for item in bad_args)
    return f'''from pathlib import Path
import pytest

from {operation.package}.cli import compute_result, main


def test_compute_result_contract():
    assert compute_result({args_literal}) == {operation.expected!r}


def test_main_writes_result(tmp_path: Path):
    target = tmp_path / "out.txt"
    assert main([{args_literal}, str(target)]) == 0
    assert target.read_text(encoding="utf-8") == {operation.expected!r}


def test_main_rejects_non_numeric_argument():
    with pytest.raises(SystemExit):
        main([{bad_args_literal}])
'''


def _numeric_arg_names(operation: SandboxOperation) -> list[str]:
    names = ["a", "b", "c", "d", "e"]
    return names[: len(operation.sample.split())]


def _stdin_stdout_cli_py(operation: SandboxOperation) -> str:
    return f'''from __future__ import annotations

import argparse
import sys


def transform(text: str) -> str:
    return {operation.expression}


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    text = sys.stdin.read() if stdin_text is None else stdin_text
    print(transform(text), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _stdin_stdout_test_py(operation: SandboxOperation) -> str:
    return f'''import pytest

from {operation.package}.cli import main, transform


def test_transform_contract():
    assert transform({operation.sample!r}) == {operation.expected!r}


def test_main_prints_stdout(capsys):
    assert main([], stdin_text={operation.sample!r}) == 0
    assert capsys.readouterr().out == {operation.expected!r}


def test_main_rejects_unexpected_argument():
    with pytest.raises(SystemExit):
        main(["unexpected"], stdin_text={operation.sample!r})
'''


def _stdin_file_cli_py(operation: SandboxOperation) -> str:
    return f'''from __future__ import annotations

import argparse
from pathlib import Path
import sys


def transform(text: str) -> str:
    return {operation.expression}


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args(argv)
    text = sys.stdin.read() if stdin_text is None else stdin_text
    Path(args.output).write_text(transform(text), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _stdin_file_test_py(operation: SandboxOperation) -> str:
    return f'''from pathlib import Path
import pytest

from {operation.package}.cli import main, transform


def test_transform_contract():
    assert transform({operation.sample!r}) == {operation.expected!r}


def test_main_writes_output(tmp_path: Path):
    target = tmp_path / "out.txt"
    assert main([str(target)], stdin_text={operation.sample!r}) == 0
    assert target.read_text(encoding="utf-8") == {operation.expected!r}


def test_main_rejects_missing_output_argument():
    with pytest.raises(SystemExit):
        main([], stdin_text={operation.sample!r})
'''


def _file_stdout_cli_py(operation: SandboxOperation) -> str:
    return f'''from __future__ import annotations

import argparse
from pathlib import Path


def transform(text: str) -> str:
    return {operation.expression}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    args = parser.parse_args(argv)
    source = Path(args.input)
    if not source.is_file():
        parser.error(f"input file does not exist: {{source}}")
    print(transform(source.read_text(encoding="utf-8")), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _file_stdout_test_py(operation: SandboxOperation) -> str:
    return f'''from pathlib import Path
import pytest

from {operation.package}.cli import main, transform


def test_transform_contract():
    assert transform({operation.sample!r}) == {operation.expected!r}


def test_main_prints_stdout(tmp_path: Path, capsys):
    source = tmp_path / "input.txt"
    source.write_text({operation.sample!r}, encoding="utf-8")
    assert main([str(source)]) == 0
    assert capsys.readouterr().out == {operation.expected!r}


def test_main_rejects_missing_input(tmp_path: Path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing.txt")])
'''


def _run(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _default_output_dir(root: Path, operation: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe = re.sub(r"[^a-z0-9_]+", "_", operation.lower()).strip("_") or "sandbox"
    return root / "artifacts" / "llm_sandbox_implementations" / f"{safe}_{stamp}"


def _python() -> str:
    import sys

    return sys.executable


def _llm_policy(*, use_model: bool) -> dict[str, Any]:
    configured = dict(sandbox_implementation_policy().get("llm_policy") or {})
    return {
        "llm_as_hypothesis_source": bool(use_model),
        "llm_output_executed_directly": configured.get("llm_output_executed_directly", False),
        "allowlisted_contract_required": configured.get("allowlisted_contract_required", True),
        "sandbox_only": configured.get("sandbox_only", True),
    }
