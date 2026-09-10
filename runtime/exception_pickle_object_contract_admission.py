"""Admission gate for source-backed exception object materializer contracts."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OBJECT_CONTRACT_ADMISSION = Path(
    "artifacts/project_development/exception_pickle_object_contract_admission.json"
)
ADMITTED_CONTRACT_KINDS = {
    "attribute_object",
    "iterable_string_list",
    "mapping_object",
    "method_object",
    "string_like",
}
SAFE_METHOD_RETURN_PROFILES = {"json", "read", "text", "decode"}


def run_exception_pickle_object_contract_admission(
    *,
    root: Path,
    object_contract_audit_path: Path,
    minimum_confidence: float = 0.7,
) -> dict[str, Any]:
    """Admit only deterministic, source-backed object contracts for replay samples."""
    root = root.resolve()
    audit = _read_json(root, object_contract_audit_path)
    cases = []
    admitted_contracts: dict[str, dict[str, Any]] = {}
    accepted_counter: Counter[str] = Counter()
    rejected_counter: Counter[str] = Counter()
    for raw_case in audit.get("cases") or []:
        if not isinstance(raw_case, dict):
            continue
        contracts = [dict(item) for item in raw_case.get("contracts") or [] if isinstance(item, dict)]
        admitted = bool(contracts) and all(_contract_admitted(item, minimum_confidence) for item in contracts)
        target_key = f"{raw_case.get('project')}::{raw_case.get('target')}"
        reasons = []
        for contract in contracts:
            kind = str(contract.get("contract_kind") or "")
            if _contract_admitted(contract, minimum_confidence):
                accepted_counter[kind] += 1
            else:
                rejected_counter[kind or "unknown"] += 1
                reasons.append(_rejection_reason(contract, minimum_confidence))
        if admitted:
            admitted_contracts[target_key] = {
                "project": raw_case.get("project"),
                "target": raw_case.get("target"),
                "contracts": contracts,
            }
        cases.append({
            "project": raw_case.get("project"),
            "target": raw_case.get("target"),
            "status": "admitted_for_replay" if admitted else "held",
            "contracts": contracts,
            "rejection_reasons": sorted(set(reasons)),
        })
    return {
        "artifact_type": "ExceptionPickleObjectContractAdmission",
        "schema_version": "exception_pickle_object_contract_admission.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "source_audit": str(object_contract_audit_path),
        "minimum_confidence": minimum_confidence,
        "admitted_contract_kinds": sorted(ADMITTED_CONTRACT_KINDS),
        "admitted_case_count": len(admitted_contracts),
        "held_case_count": len(cases) - len(admitted_contracts),
        "admitted_contract_summary": dict(sorted(accepted_counter.items())),
        "held_contract_summary": dict(sorted(rejected_counter.items())),
        "admitted_contracts": admitted_contracts,
        "cases": cases,
        "llm_authority": "advisory_only",
        "source_apply": False,
        "kb_promotion": False,
    }


def load_admitted_object_contracts(root: Path, path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = _read_json(root.resolve(), path)
    if payload.get("artifact_type") != "ExceptionPickleObjectContractAdmission":
        return {}
    if payload.get("source_apply") is not False or payload.get("kb_promotion") is not False:
        return {}
    contracts = payload.get("admitted_contracts")
    return {str(key): dict(value) for key, value in dict(contracts or {}).items() if isinstance(value, dict)}


def _contract_admitted(contract: dict[str, Any], minimum_confidence: float) -> bool:
    base_admitted = (
        str(contract.get("contract_kind") or "") in ADMITTED_CONTRACT_KINDS
        and bool(contract.get("source_backed"))
        and float(contract.get("confidence") or 0.0) >= minimum_confidence
        and contract.get("promotion_allowed") is False
    )
    if not base_admitted:
        return False
    if str(contract.get("contract_kind") or "") == "mapping_object":
        return _mapping_contract_admitted(contract)
    if str(contract.get("contract_kind") or "") == "method_object":
        return _method_contract_admitted(contract)
    return True


def _mapping_contract_admitted(contract: dict[str, Any]) -> bool:
    evidence = dict(contract.get("evidence") or {})
    keys = [str(value) for value in evidence.get("mapping_keys") or []]
    method_calls = [str(value) for value in evidence.get("method_calls") or []]
    return (
        bool(keys)
        and len(keys) <= 8
        and all(key and not key.startswith("_") for key in keys)
        and not method_calls
    )


def _method_contract_admitted(contract: dict[str, Any]) -> bool:
    evidence = dict(contract.get("evidence") or {})
    method_calls = [str(value) for value in evidence.get("method_calls") or []]
    arg_counts = {str(key): int(value or 0) for key, value in dict(evidence.get("method_call_arg_counts") or {}).items()}
    profiles = dict(evidence.get("method_return_profiles") or {})
    return (
        bool(method_calls)
        and len(method_calls) <= 3
        and all(method in SAFE_METHOD_RETURN_PROFILES for method in method_calls)
        and all(arg_counts.get(method, 1) == 0 for method in method_calls)
        and all(str(profiles.get(method) or "") in {"mapping", "string"} for method in method_calls)
    )


def _rejection_reason(contract: dict[str, Any], minimum_confidence: float) -> str:
    kind = str(contract.get("contract_kind") or "unknown")
    if kind not in ADMITTED_CONTRACT_KINDS:
        return f"contract_kind_not_admitted:{kind}"
    if not bool(contract.get("source_backed")):
        return "contract_not_source_backed"
    if float(contract.get("confidence") or 0.0) < minimum_confidence:
        return "contract_confidence_below_threshold"
    if contract.get("promotion_allowed") is not False:
        return "contract_promotion_flag_not_false"
    if kind == "mapping_object" and not _mapping_contract_admitted(contract):
        return "mapping_contract_not_literal_bounded"
    if kind == "method_object" and not _method_contract_admitted(contract):
        return "method_contract_not_bounded_zero_arg"
    return "contract_rejected"


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
