"""Level 4 human-facing project-analysis deliberation."""

from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .project_deliberation_hardening import harden_deliberation
from .project_facts import facts_from_project_report, llm_fact_digest


REQUIRED_KEYS = {
    "executive_summary",
    "capability_decomposition",
    "refactor_plan",
    "cognitive_loop",
    "open_questions",
    "confidence",
}

LOCAL_CORTEX_MODEL_IDS = {
    "local",
    "qwen-local",
    "qwen-local-cpu",
    "fast-local-cpu",
    "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
}


def deliberate_project_report(
    report: dict[str, Any],
    *,
    level35_signals: dict[str, Any] | None = None,
    config: LocalInferenceConfig | None = None,
    context_mode: str = "expanded",
) -> dict[str, Any]:
    facts = facts_from_project_report(report)
    digest = llm_fact_digest(facts)
    evidence = digest if context_mode == "compact" else facts
    signals = level35_signals or {}
    if not _is_external_cortex(config):
        fallback = _fallback_deliberation(
            digest,
            signals,
            error="external Level 4 cortex provider is required",
            config=config,
            context_mode=context_mode,
        )
        return harden_deliberation(fallback, digest)
    try:
        result = call_json_chat(_messages(evidence, signals, context_mode=context_mode), config=config)
    except LocalInferenceError as exc:
        if context_mode == "expanded" and _is_context_overflow(str(exc)):
            try:
                result = call_json_chat(_messages(digest, signals, context_mode="compact"), config=config)
            except LocalInferenceError as compact_exc:
                fallback = _fallback_deliberation(digest, signals, error=str(compact_exc), config=config, context_mode="compact_after_overflow")
                return harden_deliberation(fallback, digest)
            missing = sorted(REQUIRED_KEYS - set(result))
            if missing:
                fallback = _fallback_deliberation(
                    digest,
                    signals,
                    error=f"missing keys after compact retry: {', '.join(missing)}",
                    config=config,
                    context_mode="compact_after_overflow",
                )
                return harden_deliberation(fallback, digest)
            result = _normalize_deliberation(result)
            result["source"] = config.provider_label
            result["layer"] = "L4"
            result["model"] = config.model
            result["context_mode"] = "compact_after_overflow"
            result["fact_summary"] = digest
            result["signal_count"] = len(signals.get("signals", []))
            result["context_retry_reason"] = str(exc)
            return harden_deliberation(result, digest)
        fallback = _fallback_deliberation(digest, signals, error=str(exc), config=config, context_mode=context_mode)
        return harden_deliberation(fallback, digest)
    missing = sorted(REQUIRED_KEYS - set(result))
    if missing:
        fallback = _fallback_deliberation(digest, signals, error=f"missing keys: {', '.join(missing)}", config=config, context_mode=context_mode)
        return harden_deliberation(fallback, digest)
    result = _normalize_deliberation(result)
    result["source"] = "local_llm"
    if config and config.provider_label != "local":
        result["source"] = config.provider_label
    result["layer"] = "L4"
    result["model"] = config.model if config else None
    result["context_mode"] = context_mode
    result["fact_summary"] = digest
    result["signal_count"] = len(signals.get("signals", []))
    return harden_deliberation(result, digest)


def _messages(facts: dict[str, Any], signals: dict[str, Any], *, context_mode: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Level 4 cortex in Cognitive OS. "
                "Turn deterministic facts and Level 3.5 impulses into concise human-facing architecture interpretation. "
                "Analyze the target software project, not Cognitive OS, Level 4, or this prompt. "
                "Use only provided facts/signals. Do not invent product purpose beyond evidence. "
                "Return only JSON. No markdown fences. "
                "Use the larger Level 4 context when available, but keep response under 1200 characters. "
                "Return keys: executive_summary, capability_decomposition, refactor_plan, "
                "cognitive_loop, open_questions, confidence. confidence is high, medium, or low. "
                "executive_summary must describe the analyzed project in one sentence. "
                "Each capability must mention a concrete project feature, core file/function, protocol, schema, or data type from facts. "
                "Do not use tests, benchmarks, integration examples, docs, or CI files as capabilities. "
                "Do not write generic items like optimize pipeline, human-readable output, or integration with other libraries. "
                "Never use placeholder identifiers such as Class W, Schema Z, Function X, or Module Y. "
                "Every refactor item must name a concrete file/function and the responsibility or contract to change. "
                "If facts are weak, say what evidence is missing and set confidence to medium or low. "
                "capability_decomposition, refactor_plan, open_questions are arrays of at most 3 short strings."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Deterministic project facts ({context_mode}):\n"
                f"{json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}\n"
                "Level 3.5 impulses:\n"
                f"{json.dumps(signals, ensure_ascii=False, separators=(',', ':'))}\n"
                "Prompt contract: l4-project-interpretation-v2. Write concise Level 4 interpretation."
            ),
        },
    ]


def _is_external_cortex(config: LocalInferenceConfig | None) -> bool:
    if config is None or config.provider_label != "external_l4":
        return False
    return config.model not in LOCAL_CORTEX_MODEL_IDS


def _is_context_overflow(error: str) -> bool:
    lowered = error.lower()
    return "context" in lowered and ("exceeds" in lowered or "n_ctx" in lowered or "context size" in lowered)


def _normalize_deliberation(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    normalized["executive_summary"] = _as_short_string(normalized.get("executive_summary"))
    normalized["cognitive_loop"] = _as_short_string(normalized.get("cognitive_loop"))
    normalized["capability_decomposition"] = _as_short_list(normalized.get("capability_decomposition"))
    normalized["refactor_plan"] = _as_short_list(normalized.get("refactor_plan"))
    normalized["open_questions"] = _as_short_list(normalized.get("open_questions"))
    confidence = str(normalized.get("confidence") or "medium").lower()
    normalized["confidence"] = confidence if confidence in {"high", "medium", "low"} else "medium"
    return normalized


def _as_short_string(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value[:3])
    if value is None:
        return ""
    return str(value)


def _as_short_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value[:3]]
    if value is None:
        return []
    return [str(value)]


def _fallback_deliberation(
    facts: dict[str, Any],
    signals: dict[str, Any],
    *,
    error: str,
    config: LocalInferenceConfig | None,
    context_mode: str,
) -> dict[str, Any]:
    domain_profile = dict(facts.get("domain_profile") or {})
    frameworks = ", ".join(facts.get("frameworks", []) or [])
    project_label = frameworks or _domain_label(domain_profile) or "unknown stack"
    task = facts.get("task") or "Project purpose is not explicit in deterministic facts."
    summary = str(task) if facts.get("task") else f"{project_label} project. {task}"
    signal_rows = [row for row in signals.get("signals", []) if isinstance(row, dict)]
    capability_hints = [
        str(row.get("target") or row.get("type"))
        for row in signal_rows
        if row.get("type")
        in {
            "CAPABILITY_CANDIDATE",
            "PIPELINE_CANDIDATE",
            "RECOVERY_LOOP_CANDIDATE",
            "MVP_EXTRACTION_CANDIDATE",
            "PROCESS_BOUNDARY_CANDIDATE",
        }
    ][:3]
    refactor_hints = [_signal_refactor_hint(row) for row in _rank_refactor_signals(signal_rows)]
    refactor_hints = list(dict.fromkeys(item for item in refactor_hints if item))[:3]
    loop = facts.get("loop", []) or ["Select one entrypoint, run it, capture failure, retry/switch/stop."]
    return {
        "executive_summary": summary,
        "capability_decomposition": capability_hints or _fallback_capabilities_from_facts(facts),
        "refactor_plan": refactor_hints or ["Review entrypoints, contracts, and recovery boundaries."],
        "cognitive_loop": "; ".join(str(item) for item in loop[:3]),
        "open_questions": ["Validate boundaries and user-facing scenarios with a human reviewer."],
        "confidence": "medium",
        "source": "deterministic_fallback",
        "layer": "L4",
        "attempted_provider": config.provider_label if config else None,
        "model": config.model if config else None,
        "context_mode": context_mode,
        "fact_summary": facts,
        "signal_count": len(signal_rows),
        "fallback_reason": error,
    }


def _domain_label(domain_profile: dict[str, Any]) -> str:
    kind = str(domain_profile.get("kind") or "").replace("_", " ").strip()
    return kind if kind else ""


def _fallback_capabilities_from_facts(facts: dict[str, Any]) -> list[str]:
    runtime = dict(facts.get("runtime_extraction") or {})
    extraction = runtime.get("extraction") or []
    rows = [
        str(row.get("capability"))
        for row in extraction
        if isinstance(row, dict) and row.get("capability")
    ]
    if rows:
        return rows[:3]
    return list(facts.get("capabilities", [])[:3])


def _signal_refactor_hint(row: dict[str, Any]) -> str:
    target = str(row.get("target") or "").strip()
    action = str(row.get("suggested_action") or "").strip()
    if target and action:
        return f"{action}: {target}"
    return target or action


def _rank_refactor_signals(signal_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    useful_types = {
        "IDEMPOTENCY_RISK",
        "PROCESS_BOUNDARY_CANDIDATE",
        "MVP_EXTRACTION_CANDIDATE",
        "BROAD_FUNCTION",
        "WEAK_CONTRACT",
        "UNKNOWN_BOUNDARY",
    }
    rows = [row for row in signal_rows if row.get("type") in useful_types and row.get("target")]
    rows.sort(key=_refactor_signal_sort_key)
    selected: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    seen_groups: set[str] = set()
    for row in rows:
        signal_type = str(row.get("type") or "")
        if signal_type in seen_types:
            continue
        group = _target_group(str(row.get("target") or ""))
        if group in seen_groups:
            alternative = _first_unseen_group(rows, signal_type, seen_groups)
            if alternative is not None:
                row = alternative
                group = _target_group(str(row.get("target") or ""))
        selected.append(row)
        seen_types.add(signal_type)
        seen_groups.add(group)
        if len(selected) >= 3:
            return selected
    for row in rows:
        if row not in selected:
            selected.append(row)
        if len(selected) >= 6:
            break
    return selected


def _refactor_signal_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    signal_type = str(row.get("type") or "")
    target = str(row.get("target") or "").lower()
    type_priority = {
        "MVP_EXTRACTION_CANDIDATE": 0,
        "PROCESS_BOUNDARY_CANDIDATE": 1,
        "IDEMPOTENCY_RISK": 2,
        "BROAD_FUNCTION": 3,
        "WEAK_CONTRACT": 4,
        "UNKNOWN_BOUNDARY": 5,
    }.get(signal_type, 9)
    return (type_priority, _target_priority(signal_type, target), target)


def _first_unseen_group(rows: list[dict[str, Any]], signal_type: str, seen_groups: set[str]) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("type") or "") != signal_type:
            continue
        if _target_group(str(row.get("target") or "")) not in seen_groups:
            return row
    return None


def _target_priority(signal_type: str, target: str) -> int:
    if signal_type == "MVP_EXTRACTION_CANDIDATE":
        if any(marker in target for marker in ("send_to_model", "llm", "model", "provider")):
            return -2
        if any(marker in target for marker in ("docker_run", "docker_build")):
            return 0
        return 1
    if signal_type == "PROCESS_BOUNDARY_CANDIDATE":
        if "docker_run" in target:
            return -2
        if "docker_build" in target:
            return -1
        if "clean_docker" in target:
            return 2
        return 0
    if signal_type == "IDEMPOTENCY_RISK":
        if any(marker in target for marker in ("write_files", "copy_template", "save_to_template")):
            return -2
        if any(marker in target for marker in ("docker_run", "docker_build")):
            return 1
        return 0
    return 0


def _target_group(target: str) -> str:
    lowered = target.lower()
    if any(marker in lowered for marker in ("send_to_model", "llm", "model", "provider")):
        return "llm_boundary"
    if any(marker in lowered for marker in ("docker_run", "docker_build", "clean_docker", "subprocess")):
        return "process_boundary"
    if any(marker in lowered for marker in ("write_files", "copy_template", "save_to_template", "filesystem")):
        return "filesystem_mutation"
    return lowered
