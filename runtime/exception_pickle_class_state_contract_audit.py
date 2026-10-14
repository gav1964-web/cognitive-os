"""Class/base-state research audit for exception-pickle import-isolation cases."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BLOCKER_INTELLIGENCE = Path("artifacts/project_development/exception_pickle_blocker_intelligence_20260903T065159200878Z.json")


def run_exception_pickle_class_state_contract_audit(
    *,
    root: Path,
    blocker_intelligence_path: Path = DEFAULT_BLOCKER_INTELLIGENCE,
) -> dict[str, Any]:
    root = root.resolve()
    intelligence = _read_json(root, blocker_intelligence_path)
    cases = []
    lane_counter: Counter[str] = Counter()
    missing_counter: Counter[str] = Counter()
    for case in intelligence.get("cases") or []:
        if not isinstance(case, dict):
            continue
        profile = case.get("import_isolation_profile")
        if not isinstance(profile, dict):
            continue
        if profile.get("subtype") != "attribute_base_metaclass_risk":
            continue
        row = _case_row(case, profile)
        cases.append(row)
        lane_counter[row["research_lane"]] += 1
        missing_counter[str(profile.get("missing_import") or "unknown")] += 1
    cases.sort(key=_case_sort_key)
    return {
        "artifact_type": "ExceptionPickleClassStateContractAudit",
        "schema_version": "exception_pickle_class_state_contract_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "blocker_intelligence": str(blocker_intelligence_path),
        "case_count": len(cases),
        "research_lane_summary": dict(sorted(lane_counter.items())),
        "missing_import_summary": dict(sorted(missing_counter.items())),
        "recommended_next_lane": _recommended_lane(lane_counter),
        "cases": cases,
        "source_apply": False,
        "kb_promotion": False,
    }


def _case_row(case: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    source = dict(case.get("source_facts") or {})
    tags = set(str(tag) for tag in source.get("fact_tags") or [])
    stored = [str(value) for value in case.get("stored_constructor_inputs") or []]
    required = [str(value) for value in case.get("required_constructor_inputs") or []]
    missing_self_reads = [str(value) for value in source.get("missing_self_attribute_reads") or []]
    lane = _research_lane(profile=profile, tags=tags, missing_self_reads=missing_self_reads)
    return {
        "project": case.get("project"),
        "target": case.get("target"),
        "research_lane": lane,
        "missing_import": profile.get("missing_import") or "",
        "missing_import_kind": profile.get("missing_import_kind") or "unknown",
        "target_replay_risk": profile.get("target_replay_risk"),
        "direct_file_preferred": profile.get("direct_file_preferred"),
        "static_patch_readmission_supported": case.get("static_patch_readmission_supported") is True,
        "required_constructor_inputs": required,
        "stored_constructor_inputs": stored,
        "missing_self_attribute_reads": missing_self_reads,
        "source_fact_tags": sorted(tags),
        "next_action": _next_action(lane),
    }


def _research_lane(*, profile: dict[str, Any], tags: set[str], missing_self_reads: list[str]) -> str:
    if missing_self_reads or profile.get("has_target_self_attribute_gap") is True:
        return "target_self_state_gap_research"
    if "attribute_base_class_definition" in tags and "base_exception_argument_transform" in tags:
        return "base_constructor_passthrough_contract"
    if "attribute_base_class_definition" in tags:
        return "attribute_base_state_contract"
    return "metaclass_or_import_side_effect_contract"


def _next_action(lane: str) -> str:
    if lane == "base_constructor_passthrough_contract":
        return "derive parent constructor argument/state preservation rule before replay"
    if lane == "attribute_base_state_contract":
        return "inspect base-class attributes and forbid direct write until state map exists"
    if lane == "target_self_state_gap_research":
        return "resolve target self-attribute read/write gap before readmission"
    return "separate import side effect from metaclass/base behavior before replay"


def _recommended_lane(counter: Counter[str]) -> dict[str, Any] | None:
    if not counter:
        return None
    priority = {
        "base_constructor_passthrough_contract": 40,
        "attribute_base_state_contract": 35,
        "target_self_state_gap_research": 30,
        "metaclass_or_import_side_effect_contract": 20,
    }
    lane, count = max(counter.items(), key=lambda item: (priority.get(item[0], 0), item[1], item[0]))
    return {"research_lane": lane, "case_count": count, "priority": priority.get(lane, 0), "next_action": _next_action(lane)}


def _case_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    direct = 0 if row.get("direct_file_preferred") else 1
    risk = int(row.get("target_replay_risk") or 0)
    return (direct, risk, str(row.get("target") or ""))


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
