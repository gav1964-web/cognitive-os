"""Failure interpretation helpers for project-native intake."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .project_native_failure_target_binding import (
    _direct_test_call_targets,
    _named_constructor_failure_target,
    _production_targets,
    _test_assertion_causal_analysis,
)

_FAILED_NODE = re.compile(r"(?m)^FAILED\s+(.+?)(?:\s+-\s+.*)?$")
_ERROR_NODE = re.compile(r"(?m)^ERROR\s+(.+?)(?:\s+-\s+.*)?$")
_SUMMARY = re.compile(r"(?m)^E\s+([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::\s*(.*))?$")
_DEPENDENCY_INSTALL_HINT = re.compile(
    r"(?:do|please|try)(?:\s+to)?\s+[`'\"]?(?:python\s+-m\s+)?pip\s+install\b",
    re.IGNORECASE,
)
_ENVIRONMENT_MARKERS = (
    "error collecting",
    "importerror while importing test module",
    "modulenotfounderror:",
    "unrecognized arguments:",
    "required plugin",
    "permissionerror: [winerror 5]",
    "blockingioerror: [winerror 10035]",
    "module 'time' has no attribute 'tzset'",
    "command not found:",
    "the environment variable is longer than 32767 characters",
)

def _normalize_nodeid(nodeid: str) -> str:
    path, separator, selection = str(nodeid).partition("::")
    normalized_path = path.replace("\\", "/")
    return f"{normalized_path}{separator}{selection}" if separator else normalized_path

def _interpret_pytest_result(
    project: Path,
    exit_code: int,
    output: str,
    intake: dict[str, Any],
    *,
    environment_preparation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lowered = output.lower()
    raw_failing = list(dict.fromkeys(
        _normalize_nodeid(value)
        for value in [*_FAILED_NODE.findall(output), *_ERROR_NODE.findall(output)]
    ))
    nodeid_limit = int(intake.get("maximum_nodeid_chars") or 1024)
    failing = [value[:nodeid_limit] for value in raw_failing]
    targets = _production_targets(project, output)
    target_binding = "traceback_production_frame" if targets else None
    if not targets:
        named_constructor = _named_constructor_failure_target(project, output)
        if named_constructor:
            targets = [named_constructor]
            target_binding = "unique_named_constructor_exception"
    causal_analysis: dict[str, Any] | None = None
    if failing and not targets:
        causal_analysis = _test_assertion_causal_analysis(project, failing)
        targets = list(causal_analysis["production_targets"])
        target_binding = "unique_assertion_causal_call" if targets else None
    summary_matches = list(_SUMMARY.finditer(output))
    summary_match = summary_matches[0] if summary_matches else None
    summary = (
        f"{summary_match.group(1)}: {summary_match.group(2) or ''}".strip()
        if summary_match else _last_failure_line(output)
    )
    leaf_match = summary_matches[-1] if summary_matches else None
    leaf_summary = (
        f"{leaf_match.group(1)}: {leaf_match.group(2) or ''}".strip()
        if leaf_match else summary
    )
    if exit_code == 0:
        status = "passed"
    elif (
        exit_code in {2, 3, 4, 5}
        or any(marker in lowered for marker in _ENVIRONMENT_MARKERS)
        or _DEPENDENCY_INSTALL_HINT.search(output) is not None
        or _source_fallback_plugin_metadata_failure(output, environment_preparation)
    ):
        status = "environment_blocked"
    elif exit_code == 1 and failing:
        status = "test_failed"
    else:
        status = "unclassified_failure"
    signature_source = json.dumps(
        {"nodeids": failing, "summary": summary, "leaf_summary": leaf_summary, "targets": targets},
        sort_keys=True,
    )
    limit = int(intake.get("maximum_output_chars") or 12000)
    return {
        "status": status,
        "exit_code": exit_code,
        "failure_signature": hashlib.sha256(signature_source.encode("utf-8")).hexdigest() if status == "test_failed" else None,
        "failing_nodeids": failing[:4],
        "production_targets": targets[:8],
        "leaf_production_target": targets[-1] if targets else None,
        "target_binding": target_binding,
        "causal_analysis": causal_analysis,
        "failure_summary": summary,
        "leaf_failure_summary": leaf_summary,
        "output_tail": output[-limit:],
        "environment_reason": (
            "editable_install_required_for_plugin_metadata"
            if _source_fallback_plugin_metadata_failure(output, environment_preparation)
            else None
        ),
    }

def _source_fallback_plugin_metadata_failure(
    output: str, preparation: dict[str, Any] | None
) -> bool:
    if dict(preparation or {}).get("status") != "source_path_fallback":
        return False
    lowered = output.lower().replace("\\", "/")
    metadata_markers = (
        "entry point",
        "entry_point",
        "entrypoint",
        "unknown formatter",
        "unknown plugin",
    )
    discovery_markers = ("/plugins/", "importlib.metadata", "pkg_resources")
    return any(marker in lowered for marker in metadata_markers) and any(
        marker in lowered for marker in discovery_markers
    )

def _case_status(repetitions: list[dict[str, Any]], *, require_unique: bool) -> tuple[str, str | None]:
    if repetitions and all(row.get("status") == "passed" for row in repetitions):
        return "clean_baseline", None
    if any(row.get("status") in {"environment_blocked", "timeout", "unclassified_failure"} for row in repetitions):
        return "environment_blocked", None
    signatures = {str(row.get("failure_signature") or "") for row in repetitions}
    if not repetitions or any(row.get("status") != "test_failed" for row in repetitions) or len(signatures) != 1:
        return "unstable_failure", None
    leaves = {str(row.get("leaf_production_target") or "") for row in repetitions}
    leaves.discard("")
    if require_unique and len(leaves) != 1:
        return "reproducible_unbound_failure", None
    target = next(iter(leaves), None)
    return ("qualified_failure", target) if target else ("reproducible_unbound_failure", None)

def _last_failure_line(output: str) -> str:
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    selected = next((line for line in reversed(rows) if "error" in line.lower() or "failed" in line.lower()), "pytest failed")
    canonical = re.sub(r"\s+in\s+\d+(?:\.\d+)?s\s*$", "", selected)
    return canonical[:500]

def _failure_kind(
    target: str, summary: str, failing_nodeids: list[str] | None = None
) -> str | None:
    lowered = summary.lower()
    normalized_target = target.lower()
    if (
        lowered.startswith("typeerror:")
        and normalized_target.endswith(":socketconnectblockederror.__init__")
        and any("test_exceptions_are_pickleable" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "exception_pickle_reconstruction_contract"
    if (
        normalized_target.endswith("pytest_httpserver/httpserver.py:httpserver.start")
        and any("test_readiness_failure_stops_server" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "server_start_readiness_cleanup_contract"
    if (
        lowered.startswith('typeerror: can only concatenate str (not "int") to str')
        and normalized_target.endswith(":faker_seed")
        and any("faker_enabled_disabled" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "disabled_pytest_plugin_symbolic_seed_contract"
    if (
        lowered.startswith("attributeerror: 'nonetype' object has no attribute 'pop'")
        and normalized_target.endswith("mkdocs/theme.py:theme._load_theme_config")
    ):
        return "empty_theme_config_contract"
    if (
        lowered.startswith("assertionerror:")
        and normalized_target.endswith("src/pluggy/_hooks.py:hookcaller.call_extra")
        and any("call_extra" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "hook_extra_wrapper_order_contract"
    if (
        lowered.startswith("assertionerror:")
        and normalized_target.endswith("src/build/_builder.py:projectbuilder.metadata_path")
        and any("metadata_path" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "wheel_dist_info_content_contract"
    if (
        normalized_target.endswith(":fileprocessor.build_logical_line_tokens")
        and any("fstring_offsets" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "escaped_fstring_brace_offset_contract"
    if lowered.startswith("filenotfounderror") and "registry" in normalized_target:
        return "missing_registry_value"
    if (
        lowered.startswith("assertionerror: regex pattern did not match")
        and normalized_target.endswith(":from_timestamp")
    ):
        return "timestamp_overflow_error_contract"
    if (
        lowered.startswith("assertionerror:")
        and normalized_target.endswith(".strategy_override_if_not_empty")
        and any("falsy" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "falsy_primitive_empty_contract"
    if (
        lowered.startswith("indexerror: list index out of range")
        and normalized_target.endswith(":extract_package_name")
        and any("incomplete_import" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "incomplete_import_token_contract"
    if (
        lowered.startswith("indexerror: list index out of range")
        and normalized_target.endswith("isort/parse.py:file_contents")
        and any("ending_with_backslash" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "trailing_backslash_index_contract"
    if (
        "duplicateoptionserror: duplicate option added to command" in lowered
        and normalized_target.endswith(":main")
        and any("duplicate_option" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "duplicate_cli_short_option_contract"
    if (
        lowered.startswith("valueerror: cannot compare to string")
        and normalized_target.endswith(":option.get_help_extra")
        and any("non-string-comparable-object" in nodeid.lower() for nodeid in (failing_nodeids or []))
    ):
        return "strict_default_string_comparison_contract"
    return None
