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
