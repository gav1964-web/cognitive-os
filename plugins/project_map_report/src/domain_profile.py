"""Domain profile inference for project map answers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .doc_purpose import docs_text


def infer_domain_profile(
    summary: dict[str, Any],
    files: dict[str, Any],
    python_structure: dict[str, Any],
    routes: list[dict[str, Any]],
    imports: set[str],
) -> dict[str, Any]:
    evidence: list[str] = []
    paths = [str(item.get("path", "")) for item in python_structure.get("files", []) if isinstance(item, dict)]
    symbols = []
    for file_row in python_structure.get("files", []):
        if not isinstance(file_row, dict):
            continue
        for function in file_row.get("functions", []):
            if not isinstance(function, dict):
                continue
            symbols.append(str(function.get("name") or ""))
            symbols.extend(str(call) for call in function.get("calls", []))
    read_files = [str(item.get("path", "")) for item in files.get("files", []) if isinstance(item, dict)]
    routes_seen = {str(route.get("route", "")) for route in routes if isinstance(route, dict)}
    searchable = "\n".join(
        [
            " ".join(paths),
            " ".join(symbols),
            " ".join(read_files),
            " ".join(routes_seen),
            docs_text(files),
            " ".join(str(item) for item in imports),
        ]
    ).lower()

    kb_profile = _infer_kb_profile(searchable, summary)
    if kb_profile:
        return kb_profile

    if "/v1/chat/completions" in routes_seen or "/chat/completions" in searchable:
        evidence.append("OpenAI-compatible chat/completions route")
    if "providers.yaml" in searchable or ("provider" in searchable and "routing" in searchable):
        evidence.append("provider routing configuration")
    if "provider" in searchable and ("model" in searchable or "модель" in searchable):
        evidence.append("provider/model selection surface")
    if "arena" in searchable and "provider" in searchable:
        evidence.append("multi-provider arena/comparison surface")
    if "cache" in searchable and ("llm" in searchable or "gigachat" in searchable or "deepseek" in searchable):
        evidence.append("LLM cache surface")
    if any("providers/factory.py" in path or "api/routing.py" in path for path in paths):
        evidence.append("provider factory/routing source files")
    if imports & {"openai", "httpx", "requests", "urllib"} and "provider" in searchable:
        evidence.append("LLM/network provider imports")
    provider_markers = {"anthropic", "deepseek", "gemini", "gigachat", "openai", "qwen"} & set(_tokens(searchable))
    if provider_markers:
        evidence.append("multiple LLM provider markers")

    multi_agent_evidence: list[str] = []
    if "a2a" in searchable or "agent-to-agent" in searchable or "agent_to_agent" in searchable:
        multi_agent_evidence.append("A2A/agent-to-agent protocol evidence")
    if "agentcard" in searchable or "create_agent_card" in searchable:
        multi_agent_evidence.append("agent card/self-description evidence")
    if "consensus" in searchable or "консенсус" in searchable:
        multi_agent_evidence.append("consensus engine evidence")
    if "orchestrator" in searchable or "оркестратор" in searchable:
        multi_agent_evidence.append("orchestrator evidence")
    if "group_manager" in searchable or "группа" in searchable:
        multi_agent_evidence.append("agent group management evidence")
    if "websocket" in searchable and ("pipeline" in searchable or "agent" in searchable):
        multi_agent_evidence.append("runtime status/event surface")
    multi_agent_score = len(set(multi_agent_evidence))
    if multi_agent_score >= 3:
        return {
            "kind": "multi_agent_orchestration_runtime",
            "confidence": round(min(0.98, 0.55 + multi_agent_score * 0.1), 2),
            "evidence": sorted(set(multi_agent_evidence)),
            "transport": "FastAPI" if "FastAPI" in set(summary.get("frameworks", [])) else "unknown",
        }

    ml_evidence: list[str] = []
    if imports & {"pandas", "numpy"}:
        ml_evidence.append("tabular data processing imports")
    if imports & {"torch", "transformers", "sklearn", "sentence_transformers"}:
        ml_evidence.append("ML/model inference imports")
    if "prompts.csv" in searchable or "submission.csv" in searchable or "local_submission.csv" in searchable:
        ml_evidence.append("competition-style prompt/submission files")
    if "automodelforcausallm" in searchable or "autotokenizer" in searchable or "model.generate" in searchable:
        ml_evidence.append("local transformer generation path")
    if "faiss" in searchable or "index_mapping.pkl" in searchable or "faiss_index.bin" in searchable:
        ml_evidence.append("embedding/index retrieval artifacts")
    if "zindi" in searchable:
        ml_evidence.append("Zindi competition workspace signal")
    ml_score = len(set(ml_evidence))
    if ml_score >= 3:
        return {
            "kind": "ml_competition_inference_script",
            "confidence": round(min(0.98, 0.55 + ml_score * 0.1), 2),
            "evidence": sorted(set(ml_evidence)),
            "transport": "CLI/script",
        }

    score = len(set(evidence))
    has_chat_gateway = any(
        marker in searchable
        for marker in ("/v1/chat/completions", "/chat/completions", "chat_completions", "_handle_chat_request")
    )
    if score >= 3 and has_chat_gateway:
        return {
            "kind": "llm_provider_gateway",
            "confidence": round(min(0.98, 0.55 + score * 0.1), 2),
            "evidence": sorted(set(evidence)),
            "transport": "FastAPI" if "FastAPI" in set(summary.get("frameworks", [])) else "unknown",
        }
    repair_evidence: list[str] = []
    if "autodevagent" in searchable or "auto_dev_agent.py" in searchable:
        repair_evidence.append("AutoDevAgent control loop")
    if "docker_build" in searchable or "docker_run" in searchable or "docker compose" in searchable:
        repair_evidence.append("Docker build/run verification loop")
    if "send_to_model" in searchable or "run_prompt" in searchable:
        repair_evidence.append("LLM repair request path")
    if "write_files" in searchable or "json updates" in searchable:
        repair_evidence.append("model-proposed file update path")
    if imports & {"openai", "httpx", "requests"} and ("error" in searchable or "fix" in searchable):
        repair_evidence.append("LLM/network repair imports")
    repair_score = len(set(repair_evidence))
    if repair_score >= 3:
        return {
            "kind": "llm_auto_repair_loop",
            "confidence": round(min(0.98, 0.55 + repair_score * 0.1), 2),
            "evidence": sorted(set(repair_evidence)),
            "transport": "CLI/subprocess",
        }
    return {"kind": "generic", "confidence": 0.0, "evidence": []}


def _tokens(text: str) -> list[str]:
    return [chunk.strip(".,;:()[]{}<>/\\\"'`") for chunk in text.split()]


def _infer_kb_profile(searchable: str, summary: dict[str, Any]) -> dict[str, Any] | None:
    knowledge = _load_project_archetypes()
    best: tuple[int, dict[str, Any], list[str]] | None = None
    for rule in knowledge.get("records", []):
        if not isinstance(rule, dict):
            continue
        profile_fields_present = any(rule.get(field) for field in ("purpose_summary", "scenario_summary", "input_summary", "output_summary"))
        if not profile_fields_present:
            continue
        score, evidence = _score_kb_rule(rule, searchable, summary)
        if score <= 0:
            continue
        min_score = int(dict(rule.get("match") or {}).get("min_score") or 1)
        if score < min_score:
            continue
        priority = int(rule.get("priority") or 0)
        rank = score + priority
        if best is None or rank > best[0]:
            best = (rank, rule, evidence)
    if best is None:
        return None
    _, rule, evidence = best
    return {
        "kind": str(rule.get("archetype") or rule.get("rule_id") or "generic"),
        "confidence": round(min(0.98, 0.55 + min(len(evidence), 5) * 0.08), 2),
        "evidence": evidence,
        "transport": _transport(summary),
        "knowledge_rule": rule.get("rule_id"),
        "label": rule.get("label"),
        "purpose_summary": rule.get("purpose_summary"),
        "scenario_summary": _strings(rule.get("scenario_summary"))[:6],
        "input_summary": _strings(rule.get("input_summary"))[:8],
        "output_summary": _strings(rule.get("output_summary"))[:8],
    }


def _score_kb_rule(rule: dict[str, Any], searchable: str, summary: dict[str, Any]) -> tuple[int, list[str]]:
    match = dict(rule.get("match") or {})
    negative = [item.lower() for item in _strings(match.get("negative_contains_any"))]
    if negative and any(item in searchable for item in negative):
        return 0, []
    required = [item.lower() for item in _strings(match.get("required_contains_any"))]
    if required and not any(item in searchable for item in required):
        return 0, []
    score = 0
    evidence: list[str] = []
    text_hits = [item for item in _strings(match.get("text_contains_any")) if item.lower() in searchable]
    if text_hits:
        score += len(text_hits)
        evidence.append("matched text markers: " + ", ".join(text_hits[:5]))
    framework_hits = [
        item
        for item in _strings(match.get("framework_contains_any"))
        if item.lower() in {str(framework).lower() for framework in summary.get("frameworks", [])}
    ]
    if framework_hits:
        score += len(framework_hits)
        evidence.append("matched frameworks: " + ", ".join(framework_hits[:5]))
    return score, evidence


def _load_project_archetypes() -> dict[str, Any]:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "knowledge" / "architecture_patterns" / "project_archetypes.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"records": []}


def _transport(summary: dict[str, Any]) -> str:
    frameworks = {str(item).lower() for item in summary.get("frameworks", [])}
    if "fastapi" in frameworks:
        return "FastAPI"
    if summary.get("entrypoints"):
        return "CLI/script"
    return "unknown"


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []
