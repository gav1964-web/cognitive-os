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
from runtime.token_aware_matcher import marker_matches

@dataclass
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
        test_result = _run([_python(), "-m", "pytest", "tests", "-q", "--basetemp=.pytest-tmp"], cwd=project_dir)
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
        if any(marker_matches(lower, marker) for marker in markers):
            evidence = [marker for marker in markers if marker_matches(lower, marker)]
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
