from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.local_inference import LocalInferenceConfig, call_json_chat
from runtime.project_architecture_knowledge import load_all_knowledge_records
from runtime.role_definitions import load_role_definitions
from runtime.synthetic_role_kb_matcher import (
    STOPWORDS,
    TOKEN_ALIASES,
    _jaccard,
    _query_coverage_score,
    _record_tokens,
    _token_aware_match_score,
    _tokens,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "synthetic_role_kb_policy.json"
DEFAULT_CORPUS_PATH = ROOT / "artifacts" / "synthetic_kb_seed" / "synthetic_role_qa.json"
DEFAULT_KB_CORPUS_PATH = ROOT / "knowledge" / "role_qa" / "synthetic_role_qa.json"
def _provider_interface_questions() -> list[str]:
    subjects = [
        "какие LLM не используют OpenAI API",
        "какие провайдеры работают не через OpenAI-compatible интерфейс",
        "какие модели используют native adapter вместо OpenAIAdapter",
        "какие LLM идут через отдельный SDK или HTTP transport",
        "где отличить OpenAIAdapter от GeminiAdapter и GigaChatAdapter",
        "какой provider bypasses OpenAI-compatible chat completions client",
        "какие провайдеры требуют OAuth вместо OpenAI API key",
        "какие provider ids не должны считаться OpenAI-compatible",
        "как определить direct/native LLM integration по config/providers.yaml",
        "как ответить какие LLM работают без OpenAI API интерфейса",
        "как найти adapter_class для каждого LLM provider",
        "какие providers используют AsyncOpenAI, а какие нет",
        "где искать evidence по OpenAI-compatible и native LLM adapters",
        "как классифицировать GigaChat и Gemini по интерфейсу вызова",
        "какие LLM имеют собственный transport вместо OpenAI client",
        "как проверить что local_qwen идет через OpenAIAdapter",
        "как проверить что deepseek идет через OpenAI-compatible base_url",
        "как проверить что qwen/router providers идут через OpenAIAdapter",
        "как проверить что GigaChat не является OpenAI-compatible adapter",
        "как проверить что Gemini не является OpenAI-compatible adapter",
    ]
    suffixes = [
        "в Python проекте?",
        "по source evidence?",
        "по adapter_class в конфигурации?",
        "по imports и factory?",
        "без догадок LLM?",
        "для ProjectFactQuestionAnswers?",
        "с указанием файлов-доказательств?",
        "если вопрос задан на русском?",
        "если есть несколько routing profiles?",
        "если provider name и model name различаются?",
        "если OpenAI-compatible gateway используется для чужой модели?",
    ]
    return [f"{subject} {suffix}" for subject in subjects for suffix in suffixes]

def _provider_interface_answer(role_id: str) -> dict[str, Any]:
    return {
        "status": "candidate",
        "answer_type": "provider_interface_mapping_advisory",
        "role_id": role_id,
        "short_answer": (
            "Классифицируй LLM по adapter_class и фактическому client/transport. "
            "OpenAIAdapter/AsyncOpenAI означает OpenAI-compatible route; GeminiAdapter и GigaChatAdapter "
            "обычно являются native/direct integrations и не должны считаться OpenAI API interface."
        ),
        "recommended_steps": [
            "read provider config such as config/providers.yaml",
            "extract provider_id, adapter_class, base_url, default_model and available_models",
            "inspect provider factory for adapter_class to class mapping",
            "inspect adapter implementation imports: AsyncOpenAI means OpenAI-compatible client",
            "inspect native transports such as OAuth/httpx/provider SDK modules",
            "group providers by interface_type: openai_compatible, native_direct, unknown",
            "answer only from evidence and list files/lines when available",
            "emit controlled gap if adapter_class or implementation is missing",
        ],
        "required_evidence": [
            "config/providers.yaml provider entries",
            "provider factory adapter mapping",
            "adapter class implementation",
            "imports such as openai.AsyncOpenAI or native httpx/OAuth/SDK modules",
            "model aliases and routing profiles only as secondary evidence",
        ],
        "expected_output_shape": {
            "openai_compatible": ["provider_id/model names using OpenAIAdapter or AsyncOpenAI"],
            "native_direct": ["provider_id/model names using GeminiAdapter, GigaChatAdapter or another native adapter"],
            "unknown": ["providers without enough evidence"],
            "evidence": ["path, line, text"],
        },
        "stop_conditions": [
            "no provider configuration found",
            "adapter_class not mapped to implementation",
            "cannot distinguish provider alias from real adapter",
            "no source evidence for a claimed interface type",
        ],
        "confidence": "low",
        "limitations": [
            "synthetic seed answer; not ground truth",
            "must be checked against project evidence before use",
            "model names alone do not prove transport/interface",
        ],
    }

def _apply_feedback(record: dict[str, Any], *, outcome: str, case: dict[str, Any]) -> dict[str, Any]:
    updated = dict(record)
    feedback = dict(updated.get("feedback") or {})
    positive = int(feedback.get("positive_count") or 0)
    negative = int(feedback.get("negative_count") or 0)
    if outcome == "positive":
        positive += 1
    else:
        negative += 1
    cases = list(feedback.get("last_cases") or [])
    cases.append(
        {
            "outcome": outcome,
            "case": dict(case),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    feedback.update(
        {
            "positive_count": positive,
            "negative_count": negative,
            "last_cases": cases[-5:],
            "promotion_ready": positive >= int(load_synthetic_policy().get("minimum_confirmed_cases_for_promotion") or 3)
            and negative == 0,
        }
    )
    updated["feedback"] = feedback
    if negative > 0:
        updated["answer_state"] = "needs_review"
        updated["trust_level"] = "synthetic_seed"
    elif positive >= 3:
        updated["answer_state"] = "confirmed_candidate"
        updated["trust_level"] = "confirmed_candidate"
    elif positive >= 1:
        updated["answer_state"] = "observed_positive"
        updated["trust_level"] = "observed_candidate"
    return updated

def _source_record_id(item: dict[str, Any]) -> str | None:
    for key in ("rule_id", "pattern_id", "risk_id", "lesson_id"):
        if item.get(key):
            return str(item[key])
    return None

def _question_text(variant: str, intent: str, obj: str, item: dict[str, Any], base: dict[str, Any]) -> str:
    label = str(item.get("label") or item.get("archetype") or item.get("pattern_id") or item.get("risk_id") or obj)
    base_question = str(base.get("question") or "").strip()
    if variant == "direct":
        return f"{intent} для {obj} в контексте {label}?"
    if variant == "evidence":
        return f"Какие evidence нужны, чтобы ответить: {intent} для {obj} ({label})?"
    if variant == "risk":
        return f"Какие риски проверить перед решением: {intent} для {obj}?"
    if variant == "contract":
        return f"Какой контракт нужен для {obj}, если задача: {intent}?"
    if variant == "fallback":
        return f"Что делать, если KB не дает уверенного ответа по теме {label}?"
    return f"{base_question} Уточни применительно к {label}."

def _answer_payload(role_id: str, intent: str, obj: str, item: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    label = str(item.get("label") or item.get("archetype") or item.get("pattern_id") or item.get("risk_id") or obj)
    return {
        "status": "candidate",
        "answer_type": "role_advisory_template",
        "role_id": role_id,
        "short_answer": _short_answer(role_id, intent, obj, label),
        "recommended_steps": _steps(role_id, obj, item),
        "required_evidence": _required_evidence(role_id),
        "stop_conditions": _stop_conditions(role_id),
        "confidence": "low",
        "limitations": [
            "synthetic seed answer; not ground truth",
            "must be checked against project evidence before use",
            "cannot promote to KB without repeated confirmed cases and approval",
        ],
        "base_question_id": base.get("id"),
    }

def _short_answer(role_id: str, intent: str, obj: str, label: str) -> str:
    prefix = {
        "project_analyzer": "Сначала извлеки факты, не делай архитектурных выводов без evidence.",
        "architect": "Выбери минимальную границу изменения и зафиксируй tradeoffs.",
        "spec_writer": "Сформируй проверяемые контракты, acceptance criteria и traceability.",
        "implementer": "Планируй изолированный PatchPackage и bounded verification.",
        "tester": "Покрой контракт, негативные случаи и внешние зависимости fake-by-default.",
        "reviewer": "Проверь соответствие артефактам, риски и запрет неразрешенных мутаций.",
        "researcher": "Собери evidence candidate или KnowledgeGapPacket, не выдавай догадку за факт.",
    }.get(role_id, "Дай advisory answer с evidence gate.")
    return f"{prefix} Тема: {intent}; объект: {obj}; паттерн: {label}."

def _steps(role_id: str, obj: str, item: dict[str, Any]) -> list[str]:
    common = ["identify applicable record", "bind answer to evidence", "emit controlled gap if evidence is missing"]
    by_role = {
        "project_analyzer": ["scan source tree", "extract entrypoints/data/contracts/errors", "return ProjectMapReport facts"],
        "architect": ["rank architecture options", "choose first safe boundary", "record risks and non-goals"],
        "spec_writer": ["define input/output contracts", "write acceptance criteria", "map criteria to evidence"],
        "implementer": ["prepare change plan", "bound writable scope", "declare verification commands"],
        "tester": ["build contract test matrix", "add negative tests", "fake external calls"],
        "reviewer": ["check traceability", "block unsafe changes", "write release/rework decision"],
        "researcher": ["search official/source evidence", "record source refs", "stage KB candidate only"],
    }
    hint = str(item.get("first_slice_hint") or item.get("contract_hint") or obj)
    return [*by_role.get(role_id, []), *common, f"preferred hint: {hint}"][:8]

def _required_evidence(role_id: str) -> list[str]:
    return {
        "project_analyzer": ["source files", "entrypoints", "runtime commands"],
        "architect": ["ProjectMapReport", "source evidence", "risk patterns"],
        "spec_writer": ["ArchitectureDecisionRecord", "contract targets", "acceptance source"],
        "implementer": ["TechnicalSpec", "writable scope", "dependency policy"],
        "tester": ["TechnicalSpec", "ImplementationPlan", "testable contracts"],
        "reviewer": ["TechnicalSpec", "ImplementationPlan", "TestPlan", "TestResult if available"],
        "researcher": ["source URL or package metadata", "timestamp", "limitations"],
    }.get(role_id, ["role input artifacts"])

def _stop_conditions(role_id: str) -> list[str]:
    return {
        "project_analyzer": ["no project path", "unsupported language", "scan contract failure"],
        "architect": ["no source evidence", "unbounded mutation request"],
        "spec_writer": ["missing ADR", "unverifiable acceptance"],
        "implementer": ["source edit without approval", "unbounded patch scope"],
        "tester": ["live external calls required", "no verifiable acceptance"],
        "reviewer": ["contract violation", "unreviewed KB/source mutation"],
        "researcher": ["no evidence refs", "unattributed claim"],
    }.get(role_id, ["missing role evidence"])

def _role_intents(role_id: str) -> list[str]:
    return {
        "project_analyzer": ["определить назначение", "найти entrypoints", "описать data lifecycle", "выделить core logic", "найти side effects"],
        "architect": ["выбрать first slice", "оценить architecture boundary", "найти hidden orchestrator", "снизить replay risk", "выделить adapters"],
        "spec_writer": ["описать input/output contract", "задать acceptance criteria", "оформить error model", "описать state/replay policy", "связать требования с evidence"],
        "implementer": ["подготовить patch plan", "ограничить writable scope", "выбрать библиотеку", "собрать runnable package", "описать rollback"],
        "tester": ["составить contract tests", "составить negative tests", "замокать external provider", "проверить CLI/API", "проверить idempotency"],
        "reviewer": ["найти contract violation", "оценить release readiness", "проверить unsafe mutation", "проверить traceability", "сформировать rework decision", "заблокировать merge"],
        "researcher": ["найти официальный источник", "оформить KnowledgeGapPacket", "сравнить источники", "подготовить KB candidate", "описать limitations"],
    }.get(role_id, ["ответить на роль-специфичный вопрос"])

def _role_objects(role_id: str) -> list[str]:
    return {
        "project_analyzer": ["Python project", "CLI utility", "FastAPI service", "file-processing tool", "worker pipeline", "library package"],
        "architect": ["capability extraction", "adapter boundary", "pipeline DAG", "state model", "failure boundary", "human handoff"],
        "spec_writer": ["TechnicalSpec", "contract matrix", "acceptance suite", "data model", "error taxonomy", "handoff artifact"],
        "implementer": ["PatchPackage", "sandbox project", "dependency adapter", "CLI entrypoint", "file converter", "provider wrapper"],
        "tester": ["unit tests", "contract tests", "negative tests", "fixture set", "fake provider", "verification report"],
        "reviewer": ["ReviewFindings", "release decision", "merge block", "risk register", "traceability table", "KB promotion", "source mutation"],
        "researcher": ["official docs", "GitHub evidence", "PyPI metadata", "LLM hypothesis", "KB candidate", "knowledge gap"],
    }.get(role_id, ["role artifact"])

def _question_variants(role_id: str) -> list[str]:
    return ["direct", "evidence", "risk", "contract", "fallback", "base"]

def _tags(role_id: str, intent: str, obj: str, item: dict[str, Any]) -> list[str]:
    tags = [role_id, intent, obj, str(item.get("record_type") or "knowledge")]
    for key in ("pattern_id", "risk_id", "rule_id", "lesson_id", "archetype"):
        if item.get(key):
            tags.append(str(item[key]))
    return sorted(set(tags))

def _record_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "authority": policy.get("authority", "advisory_only"),
        "auto_promote": bool(policy.get("auto_promote", False)),
        "requires_codex_approval": bool(policy.get("requires_codex_approval", True)),
        "requires_repeated_confirmed_cases": bool(policy.get("requires_repeated_confirmed_cases", True)),
        "forbidden_uses": list(policy.get("forbidden_uses", [])),
    }

def _quality_band(score: float) -> str:
    if score >= 0.7:
        return "strong"
    if score >= 0.35:
        return "usable"
    if score > 0:
        return "weak"
    return "miss"

def _qa_id(role_id: str, question: str, answer: dict[str, Any]) -> str:
    seed = f"{role_id}:{question}:{json.dumps(answer, ensure_ascii=False, sort_keys=True)}"
    return "sqa_" + hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:16]
