"""Source-backed object contract audit for exception-pickle materializers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_active_application import DEFAULT_APPLICATION_LEDGER
from .exception_pickle_holdout_transaction import DEFAULT_AUDIT
from .exception_pickle_object_contract_advisory import (
    llm_advisory as _llm_advisory,
)
from .exception_pickle_object_contract_classifier import (
    ParameterUseVisitor as _ParameterUseVisitor,
    SAFE_ZERO_ARG_METHOD_RETURNS,
    assignment_name as _assignment_name,
    classify_parameter as _classify_parameter,
    is_join_call as _is_join_call,
    literal_string as _literal_string,
    opaque_reasons as _opaque_reasons,
    safe_method_contract as _safe_method_contract,
    unsupported_constructor_parameters,
)
from .exception_pickle_object_contract_source import (
    applied_target_keys as _applied_target_keys,
    candidate_key as _candidate_key,
    find_init as _find_init,
    read_json as _read_json,
    source_for_row as _source_for_row,
)
from .local_inference import LocalInferenceConfig

DEFAULT_OBJECT_CONTRACT_AUDIT = Path(
    "artifacts/project_development/exception_pickle_object_contract_audit.json"
)


def run_exception_pickle_object_contract_audit(
    *,
    root: Path,
    audit_path: Path = DEFAULT_AUDIT,
    application_ledger_path: Path = DEFAULT_APPLICATION_LEDGER,
    advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    """Classify remaining object-like constructor parameters from source evidence."""
    root = root.resolve()
    audit = _read_json(root, audit_path)
    ledger = _read_json(root, application_ledger_path)
    applied_keys = _applied_target_keys(ledger)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in audit.get("candidates") or []
        if isinstance(row, dict)
    }
    cases = []
    contract_counter: Counter[str] = Counter()
    advisory_counter: Counter[str] = Counter()
    for blocked in ledger.get("blocked_cases") or []:
        case = _case_for_blocked(
            root=root,
            blocked=dict(blocked or {}),
            rows_by_key=rows_by_key,
            applied_keys=applied_keys,
            advisory_config=advisory_config,
        )
        if case is None:
            continue
        for contract in case["contracts"]:
            contract_counter[contract["contract_kind"]] += 1
        advisory_counter[str(case["advisory"].get("source") or "deterministic")] += 1
        cases.append(case)
    return _report(cases, contract_counter, advisory_counter)


def _case_for_blocked(
    *,
    root: Path,
    blocked: dict[str, Any],
    rows_by_key: dict[str, dict[str, Any]],
    applied_keys: set[str],
    advisory_config: LocalInferenceConfig | None,
) -> dict[str, Any] | None:
    if blocked.get("blocker_kind") != "semantic_sample_shape_unsupported":
        return None
    key = f"{blocked.get('project')}::{blocked.get('target')}"
    if key in applied_keys:
        return None
    row = rows_by_key.get(key)
    if row is None:
        return None
    source = _source_for_row(root, row)
    if source is None:
        return None
    init_node = _find_init(source, str(row.get("class_name") or ""))
    if init_node is None:
        return None
    unsupported = unsupported_constructor_parameters(row)
    if not unsupported:
        return None
    contracts = [
        _classify_parameter(source=source, init_node=init_node, parameter=name)
        for name in unsupported
    ]
    advisory = (
        _llm_advisory(row=row, source=source, contracts=contracts, config=advisory_config)
        if advisory_config is not None and contracts
        else {"llm_invoked": False, "accepted": False, "source": "deterministic"}
    )
    return {
        "project": blocked.get("project"),
        "target": blocked.get("target"),
        "contracts": contracts,
        "advisory": advisory,
        "status": _case_status(contracts),
    }


def _report(
    cases: list[dict[str, Any]],
    contract_counter: Counter[str],
    advisory_counter: Counter[str],
) -> dict[str, Any]:
    return {
        "artifact_type": "ExceptionPickleObjectContractAudit",
        "schema_version": "exception_pickle_object_contract_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "case_count": len(cases),
        "contract_summary": dict(sorted(contract_counter.items())),
        "advisory_summary": dict(sorted(advisory_counter.items())),
        "cases": cases,
        "llm_advisory_allowed": True,
        "llm_authority": "advisory_only",
        "source_apply": False,
        "kb_promotion": False,
    }


def _case_status(contracts: list[dict[str, Any]]) -> str:
    if not contracts:
        return "no_object_contract_needed"
    if all(item["contract_kind"] != "opaque_hold" for item in contracts):
        return "source_backed_contract_candidate"
    if any(item["contract_kind"] != "opaque_hold" for item in contracts):
        return "partial_contract_candidate"
    return "object_contract_hold"


def _is_name(node: Any, name: str) -> bool:
    return getattr(node, "id", None) == name


def _contains_name(node: Any, name: str) -> bool:
    import ast

    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))
