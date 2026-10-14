"""Focused diagnostic audit for opaque exception object-contract holds."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_object_contract_admission import DEFAULT_OBJECT_CONTRACT_ADMISSION


DEFAULT_OPAQUE_HOLD_AUDIT = Path(
    "artifacts/project_development/exception_pickle_opaque_hold_audit.json"
)


def run_exception_pickle_opaque_hold_audit(
    *,
    root: Path,
    object_contract_admission_path: Path = DEFAULT_OBJECT_CONTRACT_ADMISSION,
) -> dict[str, Any]:
    """Summarize held opaque object contracts for reviewer/LLM advisory triage."""
    root = root.resolve()
    admission = _read_json(root, object_contract_admission_path)
    cases = []
    reason_counter: Counter[str] = Counter()
    parameter_counter: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for raw_case in admission.get("cases") or []:
        if not isinstance(raw_case, dict) or raw_case.get("status") != "held":
            continue
        opaque_contracts = [
            dict(contract)
            for contract in raw_case.get("contracts") or []
            if isinstance(contract, dict) and contract.get("contract_kind") == "opaque_hold"
        ]
        if not opaque_contracts:
            continue
        simplified = []
        for contract in opaque_contracts:
            parameter = str(contract.get("parameter") or "")
            evidence = dict(contract.get("evidence") or {})
            reasons = [str(value) for value in evidence.get("opaque_reasons") or []] or [
                "admission_held_without_reason"
            ]
            parameter_counter[parameter] += 1
            for reason in reasons:
                reason_counter[reason] += 1
            if len(examples[parameter]) < 3:
                examples[parameter].append({
                    "project": str(raw_case.get("project") or ""),
                    "target": str(raw_case.get("target") or ""),
                })
            simplified.append({
                "parameter": parameter,
                "opaque_reasons": reasons,
                "method_calls": list(evidence.get("method_calls") or []),
                "line_numbers": list(evidence.get("line_numbers") or []),
                "triage": _triage(reasons, evidence),
            })
        cases.append({
            "project": raw_case.get("project"),
            "target": raw_case.get("target"),
            "opaque_contracts": simplified,
            "status": "needs_advisory_or_manual_contract",
        })
    return {
        "artifact_type": "ExceptionPickleOpaqueHoldAudit",
        "schema_version": "exception_pickle_opaque_hold_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "source_admission": str(object_contract_admission_path),
        "case_count": len(cases),
        "opaque_parameter_count": sum(parameter_counter.values()),
        "reason_summary": dict(sorted(reason_counter.items())),
        "parameter_summary": {
            name: {"count": count, "examples": examples.get(name, [])}
            for name, count in parameter_counter.most_common()
        },
        "cases": cases,
        "llm_advisory_recommended": bool(cases),
        "llm_authority": "advisory_only",
        "source_apply": False,
        "kb_promotion": False,
    }


def _triage(reasons: list[str], evidence: dict[str, Any]) -> str:
    method_calls = {str(value) for value in evidence.get("method_calls") or []}
    if method_calls:
        return "inspect_method_contract"
    if "no_supported_usage_evidence" in reasons:
        return "inspect_assignment_or_alias_flow"
    return "manual_review"


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
