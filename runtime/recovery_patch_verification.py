"""Tester-owned differential verification for recovery patch packages."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .patch_synthesis_policy import (
    append_mapping_helper_recipe,
    json_dumps_helper_recipe,
    json_loads_helper_recipe,
    splitlines_helper_recipe,
)


def verify_recovery_patch_package(
    *,
    project_dir: Path,
    patch_package: dict[str, Any],
    verification_dir: Path,
) -> dict[str, Any]:
    patches = [dict(row) for row in patch_package.get("patches", []) if isinstance(row, dict)]
    if patch_package.get("status") != "prepared" or len(patches) != 1:
        return _blocked("patch_package_not_prepared")
    patch = patches[0]
    recipe = next(
        (
            row for row in (
                append_mapping_helper_recipe(),
                json_dumps_helper_recipe(),
                json_loads_helper_recipe(),
                splitlines_helper_recipe(),
            )
            if row and patch.get("kind") == row.get("operation_kind")
        ),
        {},
    )
    if not recipe:
        return _blocked("unsupported_patch_operation")
    policy = dict(recipe.get("differential_verification") or {})
    sandbox = Path(str(patch_package.get("sandbox_project") or ""))
    relative = str(patch.get("file") or "")
    if not relative or not (project_dir / relative).is_file() or not (sandbox / relative).is_file():
        return _blocked("verification_source_missing")

    runner = verification_dir / "differential_runner.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(_RUNNER, encoding="utf-8")
    rows = []
    timeout = max(1, int(policy.get("timeout_seconds") or 10))
    profile = str(policy.get("profile") or "legacy_process_all_fixture")
    target = str(patch.get("target") or "")
    _, _, symbol = target.partition(":")
    cases = [
        {"input_text": str(value), "variant": "input"}
        for value in policy.get("case_inputs") or []
    ] or [
        {"input_text": "", "variant": str(value)}
        for value in policy.get("case_variants") or []
    ]
    for index, case in enumerate(cases):
        before = _run_case(
            runner=runner,
            source_root=project_dir,
            relative=relative,
            case_dir=verification_dir / f"case_{index}" / "before",
            input_text=case["input_text"],
            profile=profile,
            symbol=symbol,
            variant=case["variant"],
            timeout=timeout,
        )
        after = _run_case(
            runner=runner,
            source_root=sandbox,
            relative=relative,
            case_dir=verification_dir / f"case_{index}" / "after",
            input_text=case["input_text"],
            profile=profile,
            symbol=symbol,
            variant=case["variant"],
            timeout=timeout,
        )
        rows.append({
            "case_id": f"differential_{index + 1}",
            "input": case["input_text"],
            "variant": case["variant"],
            "status": "passed" if before == after and before.get("status") == "ok" else "failed",
            "before": before,
            "after": after,
        })
    passed = bool(rows) and all(row["status"] == "passed" for row in rows)
    return {
        "artifact_type": "RecoveryDifferentialVerification",
        "role": "tester",
        "status": "passed" if passed else "failed",
        "patch_digest": patch_package.get("patch_digest"),
        "observations": list(policy.get("observations") or []),
        "cases": rows,
        "summary": {
            "case_count": len(rows),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] != "passed" for row in rows),
        },
        "safety": {
            "real_subprocess_calls": False,
            "isolated_case_directories": True,
            "source_project_modified": False,
        },
    }


def _run_case(
    *,
    runner: Path,
    source_root: Path,
    relative: str,
    case_dir: Path,
    input_text: str,
    profile: str,
    symbol: str,
    variant: str,
    timeout: int,
) -> dict[str, Any]:
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    (case_dir / "input.txt").write_text(input_text, encoding="utf-8")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                str((source_root / relative).resolve()),
                str(case_dir.resolve()),
                profile,
                symbol,
                variant,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    if completed.returncode != 0:
        return {"status": "failed", "stderr": completed.stderr[-1000:]}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"status": "invalid_output", "stdout": completed.stdout[-1000:]}
    return dict(payload) if isinstance(payload, dict) else {"status": "invalid_output"}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "artifact_type": "RecoveryDifferentialVerification",
        "role": "tester",
        "status": "blocked",
        "reason": reason,
        "patch_digest": None,
        "observations": [],
        "cases": [],
        "summary": {"case_count": 0, "passed": 0, "failed": 0},
        "safety": {"real_subprocess_calls": False, "source_project_modified": False},
    }


_RUNNER = r'''from __future__ import annotations
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path

source = Path(sys.argv[1])
case_dir = Path(sys.argv[2])
profile = sys.argv[3]
symbol = sys.argv[4]
variant = sys.argv[5]
os.chdir(case_dir)
spec = importlib.util.spec_from_file_location("recovery_case", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calls = []

def fake_run(*args, **kwargs):
    calls.append({"args": args, "kwargs": kwargs})
    return None

if hasattr(module, "subprocess"):
    module.subprocess.run = fake_run
try:
    function = getattr(module, symbol)
    if profile == "legacy_process_all_fixture":
        result = function()
    elif profile in {"callable_file_output", "callable_json_input", "callable_text_input"}:
        if profile == "callable_json_input":
            input_path = case_dir / "input.json"
            input_path.write_text("{}" if variant == "empty" else '{"name": "Alice", "value": 1}', encoding="utf-8")
        if profile == "callable_text_input":
            input_path = case_dir / "input.txt"
            input_path.write_text("" if variant == "empty" else "alpha\nbeta\n", encoding="utf-8")
        values = {
            "path": str(case_dir / ("input.json" if profile == "callable_json_input" else "input.txt" if profile == "callable_text_input" else "result.json")),
            "file": str(case_dir / ("input.json" if profile == "callable_json_input" else "input.txt" if profile == "callable_text_input" else "result.json")),
            "output": str(case_dir / "result.json"),
            "rows": [] if variant == "empty" else [{"name": "Alice", "value": 1}],
            "value": "" if variant == "empty" else "hello",
            "text": "" if variant == "empty" else "hello",
            "record": {} if variant == "empty" else {"name": "alice", "count": 1},
            "data": {} if variant == "empty" else {"name": "alice", "count": 1},
            "payload": {} if variant == "empty" else {"name": "alice", "count": 1},
        }
        args = []
        kwargs = {}
        for parameter in inspect.signature(function).parameters.values():
            value = values.get(parameter.name)
            if value is None:
                raise TypeError("unsupported fixture parameter: " + parameter.name)
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                args.append(value)
            else:
                kwargs[parameter.name] = value
        result = function(*args, **kwargs)
    else:
        raise TypeError("unsupported differential profile: " + profile)
    written_files = {}
    for path in sorted(case_dir.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            written_files[path.relative_to(case_dir).as_posix()] = path.read_text(encoding="utf-8")
    payload = {
        "status": "ok",
        "return_value": result,
        "subprocess_calls": calls,
        "written_files": written_files,
    }
except Exception as exc:
    payload = {"status": "exception", "exception_type": type(exc).__name__, "message": str(exc)}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
'''
