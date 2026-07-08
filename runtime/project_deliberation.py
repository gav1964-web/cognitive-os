"""Level 4 human-facing project-analysis deliberation."""

from __future__ import annotations

import json
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
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
        return _fallback_deliberation(
            digest,
            signals,
            error="external Level 4 cortex provider is required",
            config=config,
            context_mode=context_mode,
        )
    try:
        result = call_json_chat(_messages(evidence, signals, context_mode=context_mode), config=config)
    except LocalInferenceError as exc:
        if context_mode == "expanded" and _is_context_overflow(str(exc)):
            try:
                result = call_json_chat(_messages(digest, signals, context_mode="compact"), config=config)
            except LocalInferenceError as compact_exc:
                return _fallback_deliberation(digest, signals, error=str(compact_exc), config=config, context_mode="compact_after_overflow")
            missing = sorted(REQUIRED_KEYS - set(result))
            if missing:
                return _fallback_deliberation(
                    digest,
                    signals,
                    error=f"missing keys after compact retry: {', '.join(missing)}",
                    config=config,
                    context_mode="compact_after_overflow",
                )
            result = _normalize_deliberation(result)
            result["source"] = config.provider_label
            result["layer"] = "L4"
            result["model"] = config.model
            result["context_mode"] = "compact_after_overflow"
            result["fact_summary"] = digest
            result["signal_count"] = len(signals.get("signals", []))
            result["context_retry_reason"] = str(exc)
            return _harden_deliberation(result, digest)
        return _fallback_deliberation(digest, signals, error=str(exc), config=config, context_mode=context_mode)
    missing = sorted(REQUIRED_KEYS - set(result))
    if missing:
        return _fallback_deliberation(digest, signals, error=f"missing keys: {', '.join(missing)}", config=config, context_mode=context_mode)
    result = _normalize_deliberation(result)
    result["source"] = "local_llm"
    if config and config.provider_label != "local":
        result["source"] = config.provider_label
    result["layer"] = "L4"
    result["model"] = config.model if config else None
    result["context_mode"] = context_mode
    result["fact_summary"] = digest
    result["signal_count"] = len(signals.get("signals", []))
    return _harden_deliberation(result, digest)


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
                "Write concise Level 4 interpretation."
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


def _harden_deliberation(result: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    hardened = dict(result)
    warnings = []
    if _is_weak_summary(hardened.get("executive_summary")):
        hardened["executive_summary"] = _grounded_summary(facts)
        warnings.append("summary_replaced_from_facts")
    capabilities = _grounded_list(hardened.get("capability_decomposition"), facts, kind="capability")
    if capabilities != hardened.get("capability_decomposition"):
        warnings.append("capabilities_grounded")
    hardened["capability_decomposition"] = capabilities
    refactor_plan = _grounded_list(hardened.get("refactor_plan"), facts, kind="refactor")
    if refactor_plan != hardened.get("refactor_plan"):
        warnings.append("refactor_plan_grounded")
    hardened["refactor_plan"] = refactor_plan
    if not hardened.get("open_questions"):
        hardened["open_questions"] = _grounded_open_questions(facts)
        warnings.append("open_questions_added")
    if not str(hardened.get("cognitive_loop") or "").strip():
        hardened["cognitive_loop"] = _grounded_loop(facts)
        warnings.append("cognitive_loop_added")
    if _facts_are_sparse(facts) and hardened.get("confidence") == "high":
        hardened["confidence"] = "medium"
        warnings.append("confidence_reduced_for_sparse_facts")
    if warnings:
        hardened["quality_warnings"] = warnings
    return hardened


def _is_weak_summary(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text or text in {".", "...", "n/a", "unknown"}:
        return True
    generic = (
        "target software project",
        "unspecified functionality",
        "automation/tooling solution",
        "deterministic facts",
        "level 4",
        "cognitive os",
        "insert concise description",
    )
    return any(marker in text for marker in generic)


def _grounded_summary(facts: dict[str, Any]) -> str:
    task = str(facts.get("task") or "").strip()
    if task:
        return _clean_task(task)
    frameworks = ", ".join(str(item) for item in facts.get("frameworks", [])[:2])
    root = str(facts.get("root") or "project").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if frameworks:
        return f"{root} is analyzed as a {frameworks} project."
    return f"{root} has insufficient product-level evidence; review README, entrypoints, and core modules."


def _clean_task(task: str) -> str:
    text = task
    prefix = "Inferred from docs: "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    for suffix in (" (Python project).", " (Python automation/tooling project).", " (FastAPI API service).", " (Flask web application)."):
        text = text.replace(suffix, ".")
    return text.strip()


def _grounded_list(value: Any, facts: dict[str, Any], *, kind: str) -> list[str]:
    rows = [str(item) for item in value if _is_grounded_item(str(item), facts, kind=kind)] if isinstance(value, list) else []
    if rows:
        return rows[:3]
    fallback = _capability_fallback(facts) if kind == "capability" else _refactor_fallback(facts)
    return (rows + [item for item in fallback if item not in rows])[:3]


def _is_grounded_item(text: str, facts: dict[str, Any], *, kind: str) -> bool:
    lowered = text.lower()
    bad = ("optimize", "human-readable", "integration with other libraries", "pipeline", "clarity", "future")
    if any(marker in lowered for marker in bad):
        return False
    if kind == "capability" and _mentions_context_path(lowered):
        return False
    evidence = _evidence_terms(facts)
    return any(term and term in lowered for term in evidence)


def _mentions_context_path(lowered: str) -> bool:
    context = ("bench/", "benchmark", "test/", "tests/", "testing/", "test_", "testing.py", "integration/", "docs/", "ci/")
    return any(marker in lowered for marker in context)


def _evidence_terms(facts: dict[str, Any]) -> set[str]:
    terms = set()
    for key in ("task", "inputs", "outputs", "entrypoints", "capabilities", "schemas", "weak_contracts", "errors", "risks", "loop"):
        terms.update(_terms_from_value(facts.get(key)))
    for key in ("central", "broad", "hotspots"):
        terms.update(_terms_from_value(facts.get(key)))
    return {term for term in terms if len(term) >= 4}


def _terms_from_value(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_terms_from_value(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_terms_from_value(item) for item in value)) if value else set()
    text = str(value or "").replace("_", " ").replace("/", " ").replace(":", " ").replace(".", " ")
    return {part.lower() for part in text.split() if part.isalnum()}


def _capability_fallback(facts: dict[str, Any]) -> list[str]:
    rows = [str(item) for item in facts.get("capabilities", [])[:3]]
    if rows:
        return rows
    task = _clean_task(str(facts.get("task") or ""))
    entries = [str(item) for item in facts.get("entrypoints", [])[:2]]
    if "json" in task.lower():
        return ["JSON serialization/deserialization behavior evidenced by project docs"]
    if "http" in task.lower():
        return ["HTTP protocol/request handling evidenced by project docs"]
    if "ini" in task.lower():
        return ["INI configuration parsing evidenced by project docs"]
    if entries:
        return [f"Entrypoint workflow: {entry}" for entry in entries]
    return ["No safe reusable Python capability identified from current facts"]


def _refactor_fallback(facts: dict[str, Any]) -> list[str]:
    rows = []
    rows.extend(f"Review hotspot {item.get('target')}" for item in facts.get("hotspots", [])[:2] if isinstance(item, dict) and item.get("target"))
    rows.extend(f"Harden weak contract {item}" for item in facts.get("weak_contracts", [])[:2])
    if rows:
        return rows[:3]
    if not facts.get("entrypoints"):
        return ["Add or identify a product-level entrypoint before extraction"]
    return ["Map core boundaries before extracting runtime capabilities"]


def _grounded_open_questions(facts: dict[str, Any]) -> list[str]:
    questions = []
    if not facts.get("entrypoints"):
        questions.append("Which product-level entrypoint should be treated as runtime boundary?")
    if not facts.get("capabilities"):
        questions.append("Which core function is safe to extract as the first capability?")
    if facts.get("risks"):
        questions.append("Which listed risks must block automated extraction?")
    return questions[:3] or ["Which scenario should be validated first by a human reviewer?"]


def _grounded_loop(facts: dict[str, Any]) -> str:
    loop = [str(item) for item in facts.get("loop", []) if item]
    if loop:
        return "; ".join(loop[:4])
    if facts.get("entrypoints"):
        return "run entrypoint; capture input/output; inject controlled failure; report result"
    return "identify product boundary; capture representative input; test controlled failure; report extraction decision"


def _facts_are_sparse(facts: dict[str, Any]) -> bool:
    return not facts.get("entrypoints") or not facts.get("capabilities")


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
    frameworks = ", ".join(facts.get("frameworks", []) or []) or "unknown stack"
    task = facts.get("task") or "Project purpose is not explicit in deterministic facts."
    signal_rows = [row for row in signals.get("signals", []) if isinstance(row, dict)]
    capability_hints = [
        str(row.get("target") or row.get("type"))
        for row in signal_rows
        if row.get("type") in {"CAPABILITY_CANDIDATE", "PIPELINE_CANDIDATE", "RECOVERY_LOOP_CANDIDATE"}
    ][:3]
    refactor_hints = [
        str(row.get("suggested_action") or row.get("target"))
        for row in signal_rows
        if row.get("type") in {"BROAD_FUNCTION", "WEAK_CONTRACT", "UNKNOWN_BOUNDARY"}
    ][:3]
    loop = facts.get("loop", []) or ["Select one entrypoint, run it, capture failure, retry/switch/stop."]
    return {
        "executive_summary": f"{frameworks} project. {task}",
        "capability_decomposition": capability_hints or list(facts.get("capabilities", [])[:3]),
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
