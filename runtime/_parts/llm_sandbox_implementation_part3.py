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
