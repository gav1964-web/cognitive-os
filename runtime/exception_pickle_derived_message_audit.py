"""Read-only audit for derived-message exception pickle blockers."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INTELLIGENCE = Path(
    "artifacts/project_development/exception_pickle_blocker_intelligence_20260901T112027853111Z.json"
)


def run_exception_pickle_derived_message_audit(
    *,
    root: Path,
    blocker_intelligence_path: Path = DEFAULT_INTELLIGENCE,
) -> dict[str, Any]:
    root = root.resolve()
    intelligence = _read_json(root, blocker_intelligence_path)
    cases: list[dict[str, Any]] = []
    lane_counter: Counter[str] = Counter()
    signature_counter: Counter[str] = Counter()
    project_counter: Counter[str] = Counter()
    for row in intelligence.get("cases") or []:
        if not isinstance(row, dict):
            continue
        profile = dict(row.get("readmission_profile") or {})
        if profile.get("subtype") != "derived_message_sample":
            continue
        lane = _derived_lane(profile)
        lane_counter[lane] += 1
        signature_counter[str(profile.get("required_input_signature") or "")] += 1
        project_counter[str(row.get("project") or "")] += 1
        cases.append({
            "project": row.get("project"),
            "target": row.get("target"),
            "derived_message_lane": lane,
            "required_constructor_inputs": list(row.get("required_constructor_inputs") or []),
            "required_input_signature": profile.get("required_input_signature"),
            "patchable": profile.get("patchable") is True,
            "dependency_light": profile.get("dependency_light") is True,
            "ready_now": profile.get("ready_now") is True,
            "replay_risk": profile.get("replay_risk"),
            "static_patch_risk": profile.get("static_patch_risk"),
            "source_facts": row.get("source_facts") or {},
        })
    sequence = _recommended_sequence(lane_counter)
    return {
        "artifact_type": "ExceptionPickleDerivedMessageAudit",
        "schema_version": "exception_pickle_derived_message_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "blocker_intelligence": str(blocker_intelligence_path),
        "case_count": len(cases),
        "lane_summary": dict(sorted(lane_counter.items())),
        "top_required_input_signatures": _top(signature_counter, 8),
        "top_projects": _top(project_counter, 8),
        "recommended_next_lane": sequence[0] if sequence else None,
        "recommended_sequence": sequence,
        "cases": cases,
        "source_apply": False,
        "kb_promotion": False,
        "llm_authority": "advisory_only",
    }


def write_exception_pickle_derived_message_audit(
    *, root: Path, blocker_intelligence_path: Path = DEFAULT_INTELLIGENCE
) -> dict[str, Any]:
    report = run_exception_pickle_derived_message_audit(
        root=root,
        blocker_intelligence_path=blocker_intelligence_path,
    )
    output = root / "artifacts" / "project_development" / (
        "exception_pickle_derived_message_audit_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = output.as_posix()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _derived_lane(profile: dict[str, Any]) -> str:
    if profile.get("ready_now") is True:
        return "derived_message_ready_replay"
    if profile.get("patchable") is not True:
        return "derived_message_patch_shape_first"
    if profile.get("dependency_light") is not True:
        return "derived_message_import_isolation_first"
    return "derived_message_semantic_contrast"


def _recommended_sequence(counter: Counter[str]) -> list[dict[str, Any]]:
    priority = {
        "derived_message_ready_replay": 100,
        "derived_message_import_isolation_first": 80,
        "derived_message_patch_shape_first": 65,
        "derived_message_semantic_contrast": 50,
    }
    return [
        {
            "lane": lane,
            "case_count": count,
            "priority": priority.get(lane, 0),
            "next_action": _next_action(lane),
        }
        for lane, count in sorted(counter.items(), key=lambda item: (-priority.get(item[0], 0), -item[1], item[0]))
    ]


def _next_action(lane: str) -> str:
    actions = {
        "derived_message_ready_replay": "run strict bounded replay on ready derived-message cases",
        "derived_message_import_isolation_first": "improve import isolation before replaying derived-message cases",
        "derived_message_patch_shape_first": "research patch-shape support before replaying derived-message cases",
        "derived_message_semantic_contrast": "collect behavior contrast before changing materializers",
    }
    return actions.get(lane, "collect evidence")


def _top(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
