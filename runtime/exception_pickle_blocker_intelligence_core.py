"""Report assembly for exception-pickle blocker intelligence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_active_application import (
    DEFAULT_APPLICATION_LEDGER,
    _candidate_effective_replay_risk,
    _candidate_has_materializer_behavior_readmission_delta,
    _candidate_has_self_reference_args_readmission_delta,
    _candidate_has_source_aware_sample_override,
    _candidate_static_patch_risk,
)
from .exception_pickle_autonomous_shadow import _sample_constructor_value_for_source_file
from .exception_pickle_blocker_intelligence_common import (
    _candidate_key,
    _object_contracts_for_sample,
    _read_json,
    _top,
)
from .exception_pickle_blocker_intelligence_ledger import (
    _latest_active_attempt_details_by_target,
    _latest_blocked_rows_by_target,
    _semantic_replay_error,
)
from .exception_pickle_blocker_intelligence_profiles import (
    _import_isolation_profile,
    _import_isolation_summary,
    _readmission_frontier_summary,
    _readmission_profile,
)
from .exception_pickle_blocker_intelligence_routing import (
    _classify_lane,
    _recommended_sequence,
)
from .exception_pickle_blocker_intelligence_source import _source_facts
from .exception_pickle_holdout_transaction import DEFAULT_AUDIT
from .exception_pickle_object_contract_admission import load_admitted_object_contracts
from .project_development_boundary_interpreter import load_exception_pickle_patterns


def run_exception_pickle_blocker_intelligence(
    *,
    root: Path,
    audit_path: Path = DEFAULT_AUDIT,
    application_ledger_path: Path = DEFAULT_APPLICATION_LEDGER,
    object_contract_admission_path: Path | None = None,
) -> dict[str, Any]:
    """Classify blocked active-application cases into actionable next-operator lanes."""
    root = root.resolve()
    audit = _read_json(root, audit_path)
    ledger = _read_json(root, application_ledger_path)
    active_catalog = load_exception_pickle_patterns(
        str(root / "knowledge" / "role_knowledge" / "exception_pickle_reconstruction_patterns.json")
    )
    admitted_object_contracts = load_admitted_object_contracts(root, object_contract_admission_path)
    active_attempt_details = _latest_active_attempt_details_by_target(root)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in audit.get("candidates") or []
        if isinstance(row, dict)
    }
    applied_keys = {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }

    cases: list[dict[str, Any]] = []
    blocker_counter: Counter[str] = Counter()
    lane_counter: Counter[str] = Counter()
    missing_counter: Counter[str] = Counter()
    unsupported_counter: Counter[str] = Counter()
    source_fact_counter: Counter[str] = Counter()
    for blocked in _latest_blocked_rows_by_target(ledger).values():
        if not isinstance(blocked, dict):
            continue
        key = f"{blocked.get('project')}::{blocked.get('target')}"
        if key in applied_keys:
            continue
        row = rows_by_key.get(key)
        source_facts = _source_facts(root, row) if row else {}
        required = [str(value) for value in dict(row or {}).get("required_constructor_parameters") or []]
        stored = [str(value) for value in dict(row or {}).get("stored_constructor_parameters") or []]
        missing = sorted(set(required) - set(stored))
        object_contracts = _object_contracts_for_sample(admitted_object_contracts.get(key))
        source_file = root / str(dict(row or {}).get("project_root") or "") / str(dict(row or {}).get("path") or "")
        unsupported = sorted(
            name
            for name in required
            if _sample_constructor_value_for_source_file(
                name,
                source_file=source_file,
                class_name=str(dict(row or {}).get("class_name") or ""),
                object_contracts=object_contracts,
            )
            is None
        )
        source_aware_sample_override = _candidate_has_source_aware_sample_override(
            root,
            row or {},
            admitted_object_contracts,
        )
        materializer_behavior_readmission_delta = _candidate_has_materializer_behavior_readmission_delta(
            root,
            row or {},
            admitted_object_contracts,
        )
        self_reference_args_readmission_delta = _candidate_has_self_reference_args_readmission_delta(root, row or {})
        static_patch_supported = bool(
            row and not unsupported and _candidate_static_patch_risk(root, active_catalog, row) == 0
        )
        dependency_light = bool(row and _candidate_effective_replay_risk(root, row) <= 3)
        static_patch_readmission_supported = bool(static_patch_supported and dependency_light)
        lane = _classify_lane(
            blocker_kind=str(blocked.get("blocker_kind") or "unknown_blocker"),
            key=key,
            class_name=str(dict(row or {}).get("class_name") or ""),
            missing_inputs=missing,
            unsupported_inputs=unsupported,
            semantic_replay_error=_semantic_replay_error(blocked),
            source_facts=source_facts,
            admitted_object_contracts=admitted_object_contracts,
            materializer_behavior_readmission_delta=materializer_behavior_readmission_delta,
            self_reference_args_readmission_delta=self_reference_args_readmission_delta,
            static_patch_readmission_supported=static_patch_readmission_supported,
            static_patch_supported=static_patch_supported,
            dependency_light=dependency_light,
        )
        readmission_profile = (
            _readmission_profile(root, active_catalog, row, required, source_facts)
            if row and lane == "sample_supported_readmission_frontier"
            else None
        )
        import_isolation_profile = (
            _import_isolation_profile(
                root,
                row,
                blocked,
                required,
                source_facts,
                active_attempt_details.get(key) or {},
            )
            if row and lane == "import_dependency_isolation_candidate"
            else None
        )
        blocker_counter[str(blocked.get("blocker_kind") or "unknown_blocker")] += 1
        lane_counter[lane] += 1
        missing_counter.update(missing)
        unsupported_counter.update(unsupported)
        source_fact_counter.update(source_facts.get("fact_tags") or [])
        cases.append({
            "project": blocked.get("project"),
            "target": blocked.get("target"),
            "blocker_kind": blocked.get("blocker_kind"),
            "next_operator_lane": lane,
            "required_constructor_inputs": required,
            "stored_constructor_inputs": stored,
            "missing_constructor_inputs": missing,
            "unsupported_sample_inputs": unsupported,
            "source_facts": source_facts,
            "admitted_object_contract_available": key in admitted_object_contracts,
            "source_aware_sample_override": source_aware_sample_override,
            "materializer_behavior_readmission_delta": materializer_behavior_readmission_delta,
            "self_reference_args_readmission_delta": self_reference_args_readmission_delta,
            "static_patch_readmission_supported": static_patch_readmission_supported,
            "readmission_profile": readmission_profile,
            "import_isolation_profile": import_isolation_profile,
        })

    sequence = _recommended_sequence(lane_counter)
    return {
        "artifact_type": "ExceptionPickleBlockerIntelligence",
        "schema_version": "exception_pickle_blocker_intelligence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "active_application_ledger": str(application_ledger_path),
        "candidate_audit": str(audit_path),
        "blocked_case_count": len(cases),
        "blocker_summary": dict(sorted(blocker_counter.items())),
        "next_operator_lane_summary": dict(sorted(lane_counter.items())),
        "top_missing_constructor_inputs": _top(missing_counter, 12),
        "top_unsupported_sample_inputs": _top(unsupported_counter, 12),
        "source_fact_summary": dict(sorted(source_fact_counter.items())),
        "readmission_frontier_summary": _readmission_frontier_summary(cases),
        "import_isolation_summary": _import_isolation_summary(cases),
        "recommended_next_operator": sequence[0] if sequence else None,
        "recommended_sequence": sequence,
        "cases": cases,
        "source_apply": False,
        "kb_promotion": False,
        "llm_authority": "advisory_only",
    }
