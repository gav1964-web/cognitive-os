"""Level 3.5 project-analysis signal generation."""

from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .project_facts import facts_from_project_report, llm_fact_digest


REQUIRED_KEYS = {"signals"}
SIGNAL_TYPES = {
    "CAPABILITY_CANDIDATE",
    "BROAD_FUNCTION",
    "WEAK_CONTRACT",
    "ENTRYPOINT_FOUND",
    "PIPELINE_CANDIDATE",
    "RECOVERY_LOOP_CANDIDATE",
    "UNKNOWN_BOUNDARY",
    "NEEDS_HUMAN_DECISION",
    "SUBSYSTEM_HOTSPOT",
    "OWNERSHIP_BOUNDARY",
    "ARCHITECTURE_HOTSPOT",
    "MIXED_RESPONSIBILITY",
    "HIDDEN_ORCHESTRATOR",
    "IDEMPOTENCY_RISK",
    "QUARANTINE_CANDIDATE",
    "PROCESS_BOUNDARY_CANDIDATE",
    "CHECKPOINT_CANDIDATE",
    "MVP_EXTRACTION_CANDIDATE",
}


def generate_project_signals(
    report: dict[str, Any],
    *,
    config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    digest = llm_fact_digest(facts_from_project_report(report))
    deterministic_signals = _deterministic_signals(digest)
    try:
        result = call_json_chat(_messages(digest), config=config)
    except LocalInferenceError as exc:
        return {
            "signals": deterministic_signals,
            "confidence": "medium",
            "source": "deterministic_fallback",
            "layer": "L3.5",
            "fact_summary": digest,
            "deterministic_signal_count": len(deterministic_signals),
            "fallback_reason": str(exc),
        }
    missing = sorted(REQUIRED_KEYS - set(result))
    if missing:
        return {
            "signals": deterministic_signals,
            "confidence": "medium",
            "source": "deterministic_fallback",
            "layer": "L3.5",
            "fact_summary": digest,
            "deterministic_signal_count": len(deterministic_signals),
            "fallback_reason": f"project signals missing keys: {', '.join(missing)}",
        }
    llm_signals = _normalize_signals(result.get("signals", []))
    result["signals"] = _merge_signals(deterministic_signals, llm_signals, limit=20)
    result["confidence"] = str(result.get("confidence") or "medium")
    result["source"] = "local_llm"
    result["layer"] = "L3.5"
    result["fact_summary"] = digest
    result["deterministic_signal_count"] = len(deterministic_signals)
    return result


def _normalize_signals(rows: Any) -> list[dict[str, Any]]:
    signals = rows if isinstance(rows, list) else []
    normalized = []
    for row in signals[:30]:
        if not isinstance(row, dict):
            continue
        signal_type = str(row.get("type") or "NEEDS_HUMAN_DECISION")
        if signal_type not in SIGNAL_TYPES:
            signal_type = "NEEDS_HUMAN_DECISION"
        normalized.append(
            {
                "type": signal_type,
                "target": str(row.get("target") or ""),
                "severity": str(row.get("severity") or "medium"),
                "suggested_action": str(row.get("suggested_action") or ""),
                "confidence": str(row.get("confidence") or "medium"),
            }
        )
    return normalized


def _deterministic_signals(facts: dict[str, Any]) -> list[dict[str, str]]:
    signals = []
    for subsystem in facts.get("subsystems", [])[:4]:
        name = str(subsystem.get("name") or "")
        if not name:
            continue
        signals.append(
            {
                "type": "SUBSYSTEM_HOTSPOT",
                "target": name,
                "severity": _severity(subsystem.get("score"), high=18, medium=8),
                "suggested_action": "map_subsystem_boundary",
                "confidence": "high",
            }
        )
    for hotspot in facts.get("hotspots", [])[:5]:
        target = str(hotspot.get("target") or "")
        if not target:
            continue
        kind = str(hotspot.get("kind") or "hotspot")
        signal_type = "BROAD_FUNCTION" if kind == "broad_function" else "WEAK_CONTRACT" if kind == "weak_contract" else "ARCHITECTURE_HOTSPOT"
        signals.append(
            {
                "type": signal_type,
                "target": target,
                "severity": _severity(hotspot.get("weight"), high=80, medium=20),
                "suggested_action": f"inspect_{kind}",
                "confidence": "high",
            }
        )
    for boundary in facts.get("boundaries", [])[:4]:
        target = str(boundary.get("target") or "")
        if not target:
            continue
        signals.append(
            {
                "type": "OWNERSHIP_BOUNDARY",
                "target": target,
                "severity": "medium",
                "suggested_action": f"clarify_{boundary.get('kind') or 'boundary'}",
                "confidence": "high",
            }
        )
    runtime = dict(facts.get("runtime_extraction", {}))
    for item in runtime.get("mixed", [])[:3]:
        target = _target_from_item(item)
        if target:
            signals.append(_runtime_signal("MIXED_RESPONSIBILITY", target, "high", "split_mixed_responsibilities"))
    for item in runtime.get("orchestrators", [])[:3]:
        target = _target_from_item(item)
        if target:
            signals.append(_runtime_signal("HIDDEN_ORCHESTRATOR", target, "medium", "make_orchestration_explicit"))
    for item in runtime.get("idempotency", [])[:3]:
        target = str(item.get("target") or "")
        if target:
            signals.append(_runtime_signal("IDEMPOTENCY_RISK", target, "high", "add_idempotency_or_replay_guard"))
    for item in runtime.get("quarantine", [])[:3]:
        target = str(item.get("target") or "")
        if target:
            signals.append(_runtime_signal("QUARANTINE_CANDIDATE", target, "medium", "define_on_demand_quarantine_policy"))
    for item in runtime.get("process_boundary", [])[:3]:
        target = str(item.get("target") or "")
        if target:
            signals.append(_runtime_signal("PROCESS_BOUNDARY_CANDIDATE", target, "high", "prefer_process_boundary"))
    for item in runtime.get("resume", [])[:2]:
        target = str(item.get("step") or "")
        if target:
            signals.append(_runtime_signal("CHECKPOINT_CANDIDATE", target, "medium", "define_checkpoint_reuse_policy"))
    for item in runtime.get("extraction", [])[:3]:
        target = str(item.get("capability") or "")
        if target:
            signals.append(_runtime_signal("MVP_EXTRACTION_CANDIDATE", target, "high", "draft_first_pipeline_capability"))
    signals.sort(key=_signal_priority)
    return _normalize_signals(signals)


def _merge_signals(primary: list[dict[str, str]], secondary: list[dict[str, str]], *, limit: int) -> list[dict[str, str]]:
    merged = []
    seen = set()
    for signal in primary + secondary:
        key = (signal.get("type"), signal.get("target"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(signal)
        if len(merged) >= limit:
            break
    return merged


def _severity(value: Any, *, high: int, medium: int) -> str:
    try:
        numeric = int(value or 0)
    except (TypeError, ValueError):
        numeric = 0
    if numeric >= high:
        return "high"
    if numeric >= medium:
        return "medium"
    return "low"


def _signal_priority(signal: dict[str, str]) -> tuple[int, str]:
    order = {
        "IDEMPOTENCY_RISK": 0,
        "MIXED_RESPONSIBILITY": 1,
        "MVP_EXTRACTION_CANDIDATE": 2,
        "PROCESS_BOUNDARY_CANDIDATE": 3,
        "QUARANTINE_CANDIDATE": 4,
        "CHECKPOINT_CANDIDATE": 5,
        "HIDDEN_ORCHESTRATOR": 6,
        "BROAD_FUNCTION": 7,
        "SUBSYSTEM_HOTSPOT": 8,
        "OWNERSHIP_BOUNDARY": 9,
        "ARCHITECTURE_HOTSPOT": 10,
        "WEAK_CONTRACT": 11,
    }
    return (order.get(str(signal.get("type")), 50), str(signal.get("target")))


def _messages(facts: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Level 3.5 spinal pattern translator in Cognitive OS. "
                "Return short machine impulses only, not prose for a human. "
                "Use only provided deterministic facts. Return minified JSON only. "
                "Keys: signals, confidence. signals is an array of at most 12 objects. "
                "Each signal has type, target, severity, suggested_action, confidence. "
                "Allowed types: CAPABILITY_CANDIDATE, BROAD_FUNCTION, WEAK_CONTRACT, "
                "ENTRYPOINT_FOUND, PIPELINE_CANDIDATE, RECOVERY_LOOP_CANDIDATE, "
                "UNKNOWN_BOUNDARY, NEEDS_HUMAN_DECISION, SUBSYSTEM_HOTSPOT, "
                "OWNERSHIP_BOUNDARY, ARCHITECTURE_HOTSPOT, MIXED_RESPONSIBILITY, "
                "HIDDEN_ORCHESTRATOR, IDEMPOTENCY_RISK, QUARANTINE_CANDIDATE, "
                "PROCESS_BOUNDARY_CANDIDATE, CHECKPOINT_CANDIDATE, MVP_EXTRACTION_CANDIDATE. Prefer subsystem, ownership, "
                "and architecture hotspot signals over repeating entrypoints."
            ),
        },
        {
            "role": "user",
            "content": (
                "Compact deterministic facts:\n"
                f"{json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}\n"
                "Emit impulses. No explanations."
            ),
        },
    ]


def _runtime_signal(signal_type: str, target: str, severity: str, action: str) -> dict[str, str]:
    return {
        "type": signal_type,
        "target": target,
        "severity": severity,
        "suggested_action": action,
        "confidence": "high",
    }


def _target_from_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""
    path = item.get("path")
    name = item.get("name")
    return f"{path}:{name}" if path and name else str(item.get("target") or path or "")
