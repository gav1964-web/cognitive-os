"""Analyze failed report-only exception-pickle active-application probes."""

from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_autonomous_shadow import _sample_constructor_value_for_source_file
from .exception_pickle_holdout_transaction import DEFAULT_AUDIT
from .exception_pickle_active_application import DEFAULT_APPLICATION_LEDGER
from .exception_pickle_object_contract_admission import load_admitted_object_contracts


DEFAULT_REPORT_DIR = Path("artifacts/project_development")


def run_exception_pickle_failed_probe_analyzer(
    *,
    root: Path,
    audit_path: Path = DEFAULT_AUDIT,
    application_ledger_path: Path = DEFAULT_APPLICATION_LEDGER,
    object_contract_admission_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    audit = _read_json(root, audit_path)
    application_ledger = _read_optional_json(root, application_ledger_path)
    applied_targets = _applied_target_keys(application_ledger)
    admitted_contracts = load_admitted_object_contracts(root, object_contract_admission_path)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in audit.get("candidates") or []
        if isinstance(row, dict)
    }
    cases = []
    subtype_counter: Counter[str] = Counter()
    blocker_counter: Counter[str] = Counter()
    repair_lane_counter: Counter[str] = Counter()
    for attempt in _failed_report_only_probe_attempts(root):
        candidate = dict(attempt.get("candidate") or {})
        key = f"{candidate.get('project')}::{candidate.get('target')}"
        if key in applied_targets:
            continue
        row = rows_by_key.get(key, {})
        source_file = root / str(row.get("project_root") or "") / str(row.get("path") or "")
        required = [str(value) for value in row.get("required_constructor_parameters") or []]
        object_contracts = _object_contracts_for_sample(admitted_contracts.get(key))
        unsupported = sorted(
            name
            for name in required
            if _sample_constructor_value_for_source_file(
                name,
                source_file=source_file,
                class_name=str(row.get("class_name") or ""),
                object_contracts=object_contracts,
            )
            is None
        )
        source_facts = _source_facts(source_file, str(row.get("class_name") or ""), required)
        replay = dict(attempt.get("project_native_semantic_replay") or {})
        subtype = _failure_subtype(
            attempt=attempt,
            unsupported_inputs=unsupported,
            source_facts=source_facts,
            replay_error=str(replay.get("stderr") or replay.get("stdout") or ""),
        )
        repair_lane = _repair_lane(subtype)
        subtype_counter[subtype] += 1
        blocker_counter[str(attempt.get("blocker_kind") or "unknown")] += 1
        repair_lane_counter[repair_lane] += 1
        cases.append({
            "project": candidate.get("project"),
            "target": candidate.get("target"),
            "blocker_kind": attempt.get("blocker_kind"),
            "status": attempt.get("status"),
            "failed_checks": list(attempt.get("failed_checks") or []),
            "report_path": attempt.get("_report_path"),
            "required_constructor_inputs": required,
            "unsupported_sample_inputs": unsupported,
            "source_facts": source_facts,
            "failure_subtype": subtype,
            "repair_lane": repair_lane,
            "source_apply": False,
            "kb_promotion": False,
        })
    sequence = _recommended_sequence(repair_lane_counter)
    return {
        "artifact_type": "ExceptionPickleFailedProbeAnalyzer",
        "schema_version": "exception_pickle_failed_probe_analyzer.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if cases else "empty",
        "failed_probe_case_count": len(cases),
        "blocker_summary": dict(sorted(blocker_counter.items())),
        "failure_subtype_summary": dict(sorted(subtype_counter.items())),
        "repair_lane_summary": dict(sorted(repair_lane_counter.items())),
        "recommended_next_repair_lane": sequence[0] if sequence else None,
        "recommended_sequence": sequence,
        "cases": cases,
        "source_apply": False,
        "kb_promotion": False,
    }


def _failed_report_only_probe_attempts(root: Path) -> list[dict[str, Any]]:
    report_dir = root / DEFAULT_REPORT_DIR
    if not report_dir.is_dir():
        return []
    attempts_by_key: dict[str, dict[str, Any]] = {}
    for path in sorted(report_dir.glob("exception_pickle_active_application_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(report, dict) or report.get("artifact_type") != "ExceptionPickleActiveApplicationTrial":
            continue
        if report.get("update_application_ledger") is not False:
            continue
        generated_at = str(report.get("generated_at") or path.name)
        for attempt in report.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            candidate = dict(attempt.get("candidate") or {})
            key = f"{candidate.get('project')}::{candidate.get('target')}"
            enriched = dict(attempt)
            enriched["_generated_at"] = generated_at
            enriched["_report_path"] = path.as_posix()
            previous = attempts_by_key.get(key)
            if previous is None or str(previous.get("_generated_at") or "") <= generated_at:
                attempts_by_key[key] = enriched
    return [
        attempt
        for attempt in sorted(
            attempts_by_key.values(),
            key=lambda row: (str(row.get("_generated_at") or ""), str(row.get("_report_path") or "")),
        )
        if attempt.get("status") != "applied_active_kb"
    ]


def _failure_subtype(
    *,
    attempt: dict[str, Any],
    unsupported_inputs: list[str],
    source_facts: dict[str, Any],
    replay_error: str,
) -> str:
    blocker = str(attempt.get("blocker_kind") or "")
    tags = set(source_facts.get("fact_tags") or [])
    if blocker == "semantic_sample_shape_unsupported":
        if not unsupported_inputs:
            return "stale_probe_now_sample_supported"
        if "exception_alias_parameter" in tags:
            return "exception_alias_parameter_sample_gap"
        if "command_name_access" in tags:
            return "command_like_object_sample_gap"
        return "unsupported_constructor_sample_shape"
    if blocker == "semantic_replay_behavior_mismatch":
        if (
            "missing 2 required positional arguments" in replay_error
            and "base_constructor_passthrough" in tags
        ):
            return "base_constructor_passthrough_contract_gap"
        if "RecursionError" in replay_error and "self_referential_super_init" in tags:
            return "self_referential_super_init_object_state_replay_gap"
        if "RecursionError" in replay_error:
            return "recursive_replay_result_serialization_gap"
        return "semantic_behavior_mismatch_under_direct_file_probe"
    return "failed_probe_unclassified"


def _repair_lane(subtype: str) -> str:
    if subtype in {
        "exception_alias_parameter_sample_gap",
        "command_like_object_sample_gap",
        "unsupported_constructor_sample_shape",
    }:
        return "source_backed_sample_materializer_repair"
    if subtype == "stale_probe_now_sample_supported":
        return "active_application_reprobe"
    if subtype in {
        "self_referential_super_init_object_state_replay_gap",
        "recursive_replay_result_serialization_gap",
    }:
        return "semantic_replay_capture_repair"
    if subtype == "semantic_behavior_mismatch_under_direct_file_probe":
        return "semantic_behavior_contrast_research"
    if subtype == "base_constructor_passthrough_contract_gap":
        return "constructor_state_contract_research"
    return "failed_probe_research"


def _recommended_sequence(counter: Counter[str]) -> list[dict[str, Any]]:
    priorities = {
        "source_backed_sample_materializer_repair": 90,
        "active_application_reprobe": 85,
        "semantic_replay_capture_repair": 80,
        "semantic_behavior_contrast_research": 50,
        "constructor_state_contract_research": 35,
        "failed_probe_research": 10,
    }
    return [
        {
            "repair_lane": lane,
            "case_count": count,
            "priority": priorities.get(lane, 0),
            "next_action": _next_action(lane),
        }
        for lane, count in sorted(
            counter.items(),
            key=lambda item: (-priorities.get(item[0], 0), -item[1], item[0]),
        )
    ]


def _next_action(lane: str) -> str:
    actions = {
        "source_backed_sample_materializer_repair": (
            "add narrowly source-backed samples for observed constructor object shapes"
        ),
        "semantic_replay_capture_repair": (
            "make replay result capture cycle-safe before widening acceptance"
        ),
        "active_application_reprobe": (
            "rerun report-only probes because current samples now satisfy the old precheck"
        ),
        "semantic_behavior_contrast_research": (
            "compare before/after behavior before considering an operator change"
        ),
        "constructor_state_contract_research": (
            "research parent constructor state requirements before readmission"
        ),
    }
    return actions.get(lane, "collect failed probe source evidence")


def _source_facts(source_file: Path, class_name: str, parameters: list[str]) -> dict[str, Any]:
    if not source_file.is_file() or not class_name:
        return {"available": False, "fact_tags": ["source_missing"]}
    try:
        source = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = source_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"available": False, "fact_tags": ["source_missing"]}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"available": False, "fact_tags": ["source_parse_failed"]}
    class_node = next(
        (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name),
        None,
    )
    init_node = next(
        (
            node
            for node in (class_node.body if class_node else [])
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        ),
        None,
    )
    if init_node is None:
        return {"available": False, "fact_tags": ["init_missing"]}
    visitor = _ProbeFactVisitor(set(parameters))
    visitor.visit(init_node)
    return {
        "available": True,
        "fact_tags": sorted(visitor.fact_tags),
        "self_assignments": dict(sorted(visitor.self_assignments.items())),
        "parameter_attribute_accesses": dict(sorted(visitor.parameter_attribute_accesses.items())),
        "super_init_arguments": visitor.super_init_arguments,
    }


class _ProbeFactVisitor(ast.NodeVisitor):
    def __init__(self, parameters: set[str]) -> None:
        self.parameters = parameters
        self.fact_tags: set[str] = set()
        self.self_assignments: dict[str, str] = {}
        self.parameter_attribute_accesses: dict[str, list[str]] = {}
        self.super_init_arguments: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id in self.parameters:
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    self.self_assignments[target.attr] = node.value.id
                    if target.attr in {"original", "cause"}:
                        self.fact_tags.add("exception_alias_parameter")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id in self.parameters:
            self.parameter_attribute_accesses.setdefault(node.value.id, []).append(node.attr)
            if node.attr == "name":
                self.fact_tags.add("command_name_access")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if _is_super_init_call(node):
            args = [_node_text(arg) for arg in node.args]
            self.super_init_arguments.extend(args)
            if any(isinstance(arg, ast.Name) and arg.id == "self" for arg in node.args):
                self.fact_tags.add("self_referential_super_init")
            if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
                keyword.arg is None for keyword in node.keywords
            ):
                self.fact_tags.add("base_constructor_passthrough")
        self.generic_visit(node)


def _is_super_init_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "__init__"
        and isinstance(func.value, ast.Call)
        and isinstance(func.value.func, ast.Name)
        and func.value.func.id == "super"
    )


def _node_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _object_contracts_for_sample(entry: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not entry:
        return {}
    return {
        str(contract.get("parameter")): dict(contract)
        for contract in entry.get("contracts") or []
        if isinstance(contract, dict) and contract.get("parameter")
    }


def _candidate_key(row: dict[str, Any]) -> str:
    project = row.get("canonical_project") or row.get("project")
    target = f"{row.get('path')}:{row.get('class_name')}.__init__"
    return f"{project}::{target}"


def _applied_target_keys(application_ledger: dict[str, Any]) -> set[str]:
    return {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in application_ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload


def _read_optional_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    if not resolved.exists():
        return {}
    return _read_json(root, path)
