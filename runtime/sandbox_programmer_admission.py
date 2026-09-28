"""Tester/Reviewer admission for bounded sandbox programmer packages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sandbox_release_policy import load_sandbox_release_policy, required_checks
from .sandbox_programmer_profiles import admission_shape


def review_sandbox_programmer_result(result: dict[str, Any]) -> dict[str, Any]:
    """Review a sandbox implementation result without granting source-apply authority."""

    project_dir = Path(str(result.get("project_dir") or ""))
    files = [str(item) for item in result.get("files", [])]
    texts = _read_texts(project_dir, files)
    source_text = "\n".join(texts.get(item, "") for item in files if item.startswith("src/") and item.endswith(".py"))
    test_text = "\n".join(texts.get(item, "") for item in files if item.startswith("tests/") and item.endswith(".py"))
    readme = texts.get("README.md", "")
    operation = dict(dict(result.get("implementation_plan", {})).get("operation", {}))
    profile = str(operation.get("profile") or "file_transform")
    shape = admission_shape(profile)
    cli_accepts_input_output = 'add_argument("input"' in source_text and 'add_argument("output"' in source_text
    cli_accepts_file_stdout = shape == "file_stdout" and 'add_argument("input"' in source_text
    cli_accepts_stdin_stdout = shape == "stdin_stdout" and "sys.stdin.read" in source_text and "stdin_text" in source_text
    cli_accepts_stdin_file = (
        shape == "stdin_file"
        and "sys.stdin.read" in source_text
        and 'add_argument("output"' in source_text
    )
    cli_accepts_numeric_args = (
        shape in {"numeric_args_stdout", "numeric_args_file"}
        and (
            ('add_argument("first"' in source_text and 'add_argument("second"' in source_text)
            or ('add_argument("a"' in source_text and 'add_argument("b"' in source_text)
        )
    )
    cli_accepts_numeric_file = shape == "numeric_args_file" and cli_accepts_numeric_args and 'add_argument("output"' in source_text
    has_transform_contract_test = "test_transform_contract" in test_text or (
        shape in {"numeric_args_stdout", "numeric_args_file"}
        and ("test_compute_sum_contract" in test_text or "test_compute_result_contract" in test_text)
    )
    has_cli_output_test = "test_cli_writes_output" in test_text or (
        shape == "numeric_args_stdout"
        and ("test_main_prints_sum" in test_text or "test_main_prints_result" in test_text)
        and "capsys" in test_text
    ) or (
        shape in {"numeric_args_file", "stdin_file"} and "test_main_writes" in test_text
    ) or (
        shape in {"stdin_stdout", "file_stdout"} and "test_main_prints_stdout" in test_text and "capsys" in test_text
    )
    available_checks = {
        "sandbox_result_verified": dict(result.get("verification", {})).get("status") == "passed",
        "has_pyproject": "pyproject.toml" in files,
        "has_readme": "README.md" in files and bool(readme.strip()),
        "has_source_cli": any(item.startswith("src/") and item.endswith("/cli.py") for item in files),
        "has_tests": any(item.startswith("tests/") and item.endswith(".py") for item in files),
        "has_fixture_evidence": any("/fixtures/" in item.replace("\\", "/") for item in files),
        "cli_uses_argparse": "import argparse" in source_text and "parse_args" in source_text,
        "cli_accepts_input_output": (
            cli_accepts_input_output
            or cli_accepts_numeric_file
            or cli_accepts_numeric_args
            or cli_accepts_file_stdout
            or cli_accepts_stdin_stdout
            or cli_accepts_stdin_file
        ),
        "has_transform_contract_test": has_transform_contract_test,
        "has_cli_output_test": has_cli_output_test,
        "has_negative_test": "missing" in test_text.lower() or "raises" in test_text.lower(),
        "readme_has_run_command": "python -m" in readme and "pytest" in readme,
        "promotion_still_forbidden": result.get("promotion_allowed") is False,
        "source_tree_unchanged": result.get("source_code_changes") is False,
        "registry_unchanged": result.get("registry_changes") is False,
        "llm_output_not_executed_directly": dict(result.get("llm_policy", {})).get("llm_output_executed_directly") is False,
    }
    checks = {check: available_checks.get(check, False) for check in required_checks("sandbox_programmer_admission")}
    failed = [name for name, ok in checks.items() if not ok]
    policy = dict(load_sandbox_release_policy().get("sandbox_programmer_admission") or {})
    recommendation_policy = dict(policy.get("recommendation") or {})
    release_policy = dict(policy.get("release_decision") or {})
    passed = not failed
    recommendation = str(recommendation_policy.get("passed" if passed else "failed") or ("approve_with_risks" if passed else "request_rework"))
    return {
        "artifact_type": "SandboxProgrammerAdmission",
        "role": "tester_reviewer",
        "status": "passed" if passed else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": result.get("project_dir"),
        "checks": checks,
        "failed_checks": failed,
        "recommendation": recommendation,
        "release_candidate": passed,
        "release_decision": {
            "decision": str(release_policy.get("passed" if passed else "failed") or ("release_ready_with_risks" if passed else "blocked")),
            "reason": str(release_policy.get("passed_reason" if passed else "failed_reason") or ""),
        },
        "known_limitations": [str(item) for item in policy.get("known_limitations", [])],
        "forbidden_actions_enforced": [str(item) for item in policy.get("forbidden_actions_enforced", [])],
    }


def _read_texts(project_dir: Path, files: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not project_dir:
        return texts
    try:
        root = project_dir.resolve()
    except OSError:
        return texts
    for item in files:
        path = (project_dir / item).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.suffix.lower() not in {".py", ".md", ".txt", ".toml"}:
            continue
        if path.is_file():
            texts[item] = path.read_text(encoding="utf-8", errors="replace")
    return texts
