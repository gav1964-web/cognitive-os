"""Synthetic role-scoped Q/A seed corpus.

The corpus is deliberately advisory: it bootstraps retrieval coverage without
pretending to be verified project evidence or a promoted KB record.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, call_json_chat
from .project_architecture_knowledge import load_all_knowledge_records
from .role_definitions import load_role_definitions


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "synthetic_role_kb_policy.json"
DEFAULT_CORPUS_PATH = ROOT / "artifacts" / "synthetic_kb_seed" / "synthetic_role_qa.json"
DEFAULT_KB_CORPUS_PATH = ROOT / "knowledge" / "role_qa" / "synthetic_role_qa.json"


class SyntheticRoleKbError(RuntimeError):
    """Raised when synthetic KB input or policy is invalid."""


@dataclass(frozen=True)
class SyntheticRoleQaRecord:
    record_type: str
    qa_id: str
    role_id: str
    role_label: str
    question: str
    answer: dict[str, Any]
    answer_state: str
    tags: list[str]
    origin: dict[str, Any]
    feedback: dict[str, Any]
    source_template: str
    trust_level: str
    evidence_strength: str
    policy: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "qa_id": self.qa_id,
            "role_id": self.role_id,
            "role_scope": [self.role_id],
            "role_label": self.role_label,
            "question": self.question,
            "answer": self.answer,
            "answer_state": self.answer_state,
            "tags": list(self.tags),
            "origin": dict(self.origin),
            "feedback": dict(self.feedback),
            "source_template": self.source_template,
            "trust_level": self.trust_level,
            "evidence_strength": self.evidence_strength,
            "policy": dict(self.policy),
            "created_at": self.created_at,
        }


def load_synthetic_policy(path: Path | None = None) -> dict[str, Any]:
    source = path or POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "synthetic_role_kb_policy.v1":
        raise SyntheticRoleKbError("synthetic role KB policy schema mismatch")
    if payload.get("status") != "active":
        raise SyntheticRoleKbError("synthetic role KB policy must be active")
    return payload


def generate_synthetic_role_qa(
    *,
    records_per_role: int | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_synthetic_policy()
    count = int(records_per_role or policy.get("default_records_per_role") or 1000)
    if count <= 0:
        raise SyntheticRoleKbError("records_per_role must be positive")
    roles = load_role_definitions()
    knowledge = _knowledge_items()
    records: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()
    for role in roles:
        role_records = _records_for_role(
            role_id=role.role_id,
            role_label=role.label,
            count=count,
            base_questions=role.questions,
            knowledge=knowledge,
            policy=policy,
            created_at=created_at,
        )
        records.extend(record.to_dict() for record in role_records)
    topic_records = _provider_interface_seed_records(policy=policy, created_at=created_at)
    records.extend(record.to_dict() for record in topic_records)
    return {
        "artifact_type": "SyntheticRoleQACorpus",
        "schema_version": "synthetic_role_qa.v1",
        "created_at": created_at,
        "records_per_role": count,
        "role_count": len(roles),
        "topic_record_count": len(topic_records),
        "record_count": len(records),
        "policy": _record_policy(policy),
        "records": records,
    }


def write_synthetic_role_qa(
    *,
    root: Path | None = None,
    output: Path | None = None,
    records_per_role: int | None = None,
) -> Path:
    root = root or ROOT
    path = output or DEFAULT_KB_CORPUS_PATH
    if not path.is_absolute():
        path = root / path
    corpus = generate_synthetic_role_qa(records_per_role=records_per_role)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def write_llm_role_qa(
    *,
    root: Path | None = None,
    output: Path | None = None,
    records_per_role: int = 20,
    append: bool = True,
    config: LocalInferenceConfig | None = None,
) -> Path:
    root = root or ROOT
    path = output or DEFAULT_KB_CORPUS_PATH
    if not path.is_absolute():
        path = root / path
    base = load_synthetic_role_qa(path) if append and path.is_file() else _empty_corpus()
    llm_records = generate_llm_role_qa(records_per_role=records_per_role, config=config)
    existing = [row for row in base.get("records", []) if isinstance(row, dict)]
    existing_by_id = {str(row.get("qa_id")): row for row in existing if row.get("qa_id")}
    for record in llm_records["records"]:
        existing_by_id[str(record["qa_id"])] = record
    base["records"] = list(existing_by_id.values())
    base["record_count"] = len(base["records"])
    base["llm_record_count"] = sum(1 for row in base["records"] if dict(row).get("origin", {}).get("kind") == "llm_synthetic_seed")
    base["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def generate_llm_role_qa(
    *,
    records_per_role: int = 20,
    config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    if records_per_role <= 0:
        raise SyntheticRoleKbError("records_per_role must be positive")
    policy = load_synthetic_policy()
    roles = load_role_definitions()
    created_at = datetime.now(timezone.utc).isoformat()
    cfg = config or LocalInferenceConfig.from_l45_env()
    records: list[dict[str, Any]] = []
    for role in roles:
        seen_questions: set[str] = set()
        for index in range(records_per_role):
            response = call_json_chat(
                _llm_generation_messages(role.to_dict(), 1, index=index, seen_questions=sorted(seen_questions)[-8:]),
                config=cfg,
            )
            rows = response.get("records")
            if not isinstance(rows, list):
                raise SyntheticRoleKbError(f"LLM did not return records array for role {role.role_id}")
            row = rows[0] if rows else {}
            if not isinstance(row, dict):
                continue
            question = str(row.get("question") or "").strip()
            answer = row.get("answer") if isinstance(row.get("answer"), dict) else {}
            if not question or not answer:
                continue
            seen_questions.add(question)
            hardened = _harden_llm_answer(role.role_id, answer)
            record = SyntheticRoleQaRecord(
                record_type="role_qa",
                qa_id=_qa_id(role.role_id, question, hardened),
                role_id=role.role_id,
                role_label=role.label,
                question=question,
                answer=hardened,
                answer_state="seeded",
                tags=sorted(set([role.role_id, "llm_generated", *[str(tag) for tag in row.get("tags", []) if tag]])),
                origin={
                    "kind": "llm_synthetic_seed",
                    "generator": "runtime.synthetic_role_kb.generate_llm_role_qa",
                    "model": cfg.model,
                    "base_url": cfg.base_url,
                    "prompt_profile": "role_qa_generation.v1",
                    "source_knowledge_record": None,
                    "base_question_id": None,
                },
                feedback={
                    "positive_count": 0,
                    "negative_count": 0,
                    "last_cases": [],
                    "promotion_ready": False,
                },
                source_template="llm_role_qa_generation",
                trust_level=str(policy.get("trust_level") or "synthetic_seed"),
                evidence_strength=str(policy.get("evidence_strength") or "synthetic"),
                policy=_record_policy(policy),
                created_at=created_at,
            )
            records.append(record.to_dict())
    return {
        "artifact_type": "SyntheticRoleQACorpus",
        "schema_version": "synthetic_role_qa.v1",
        "created_at": created_at,
        "records_per_role": records_per_role,
        "role_count": len(roles),
        "record_count": len(records),
        "llm_record_count": len(records),
        "policy": _record_policy(policy),
        "records": records,
    }


def load_synthetic_role_qa(path: Path | None = None) -> dict[str, Any]:
    source = path or DEFAULT_KB_CORPUS_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "synthetic_role_qa.v1":
        raise SyntheticRoleKbError("synthetic role QA corpus schema mismatch")
    records = payload.get("records")
    if not isinstance(records, list):
        raise SyntheticRoleKbError("synthetic role QA corpus requires records")
    return payload


def role_qa_records_from_kb(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or DEFAULT_KB_CORPUS_PATH
    if not source.is_file():
        return []
    return [dict(row) for row in load_synthetic_role_qa(source).get("records", []) if isinstance(row, dict)]


def synthetic_role_qa_summary(corpus: dict[str, Any]) -> dict[str, Any]:
    records = [dict(row) for row in corpus.get("records", []) if isinstance(row, dict)]
    by_role = Counter(str(row.get("role_id")) for row in records)
    by_trust = Counter(str(row.get("trust_level")) for row in records)
    by_state = Counter(str(row.get("answer_state")) for row in records)
    return {
        "artifact_type": "SyntheticRoleQASummary",
        "record_count": len(records),
        "by_role": dict(sorted(by_role.items())),
        "by_trust_level": dict(sorted(by_trust.items())),
        "by_answer_state": dict(sorted(by_state.items())),
        "policy": dict(corpus.get("policy") or {}),
    }


def search_synthetic_role_qa(
    query: str,
    *,
    role_id: str | None = None,
    corpus: dict[str, Any] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    corpus = corpus or load_synthetic_role_qa()
    query_tokens = _tokens(query)
    rows = []
    for record in corpus.get("records", []):
        if not isinstance(record, dict):
            continue
        if role_id and str(record.get("role_id")) != role_id:
            continue
        haystack = " ".join(
            [
                str(record.get("question") or ""),
                " ".join(str(tag) for tag in record.get("tags", [])),
                json.dumps(record.get("answer") or {}, ensure_ascii=False),
            ]
        )
        score = _query_coverage_score(query_tokens, _tokens(haystack))
        if score <= 0:
            continue
        rows.append({"score": round(score, 4), **record})
    rows.sort(key=lambda row: (-float(row["score"]), str(row.get("qa_id"))))
    return {
        "artifact_type": "SyntheticRoleQASearchResult",
        "query": query,
        "role_id": role_id,
        "match_count": len(rows),
        "matches": rows[:limit],
        "policy": dict(corpus.get("policy") or {}),
    }


def record_role_qa_feedback(
    *,
    qa_id: str,
    outcome: str,
    case: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    source = path or DEFAULT_KB_CORPUS_PATH
    corpus = load_synthetic_role_qa(source)
    outcome = str(outcome).strip().lower()
    if outcome not in {"positive", "negative"}:
        raise SyntheticRoleKbError("feedback outcome must be positive or negative")
    records = list(corpus.get("records", []))
    updated = None
    for record in records:
        if not isinstance(record, dict) or str(record.get("qa_id")) != qa_id:
            continue
        updated = _apply_feedback(record, outcome=outcome, case=case or {})
        record.clear()
        record.update(updated)
        break
    if updated is None:
        raise SyntheticRoleKbError(f"role QA record not found: {qa_id}")
    source.write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "artifact_type": "SyntheticRoleQAFeedbackUpdate",
        "status": "ok",
        "qa_id": qa_id,
        "outcome": outcome,
        "answer_state": updated.get("answer_state"),
        "trust_level": updated.get("trust_level"),
        "feedback": updated.get("feedback"),
        "path": source.as_posix(),
    }


def synthetic_probe_report(corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    corpus = corpus or load_synthetic_role_qa()
    probes = [
        ("project_analyzer", "какие entrypoints есть в проекте и где начинается execution path"),
        ("architect", "какую архитектурную границу выбрать и какие риски учесть"),
        ("spec_writer", "какие контракты и acceptance criteria нужны для ТЗ"),
        ("implementer", "как подготовить patch package и не менять исходники без разрешения"),
        ("tester", "какие negative tests и contract tests нужны"),
        ("reviewer", "что блокирует merge и какие риски остались"),
        ("researcher", "что делать если не хватает информации и нужен внешний источник"),
    ]
    rows = []
    for role_id, query in probes:
        result = search_synthetic_role_qa(query, role_id=role_id, corpus=corpus, limit=3)
        rows.append(
            {
                "role_id": role_id,
                "query": query,
                "match_count": result["match_count"],
                "top_score": result["matches"][0]["score"] if result["matches"] else 0,
                "quality": _quality_band(result["matches"][0]["score"] if result["matches"] else 0),
                "top_question": result["matches"][0]["question"] if result["matches"] else None,
            }
        )
    return {
        "artifact_type": "SyntheticRoleQAProbeReport",
        "probe_count": len(rows),
        "covered": sum(1 for row in rows if row["match_count"] > 0),
        "rows": rows,
        "policy": dict(corpus.get("policy") or {}),
    }


def _records_for_role(
    *,
    role_id: str,
    role_label: str,
    count: int,
    base_questions: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
    policy: dict[str, Any],
    created_at: str,
) -> list[SyntheticRoleQaRecord]:
    records = []
    intents = _role_intents(role_id)
    objects = _role_objects(role_id)
    variants = _question_variants(role_id)
    index = 0
    while len(records) < count:
        base = base_questions[index % len(base_questions)] if base_questions else {}
        item = knowledge[index % len(knowledge)]
        intent = intents[index % len(intents)]
        obj = objects[(index // len(intents)) % len(objects)]
        variant = variants[(index // (len(intents) * len(objects))) % len(variants)]
        question = _question_text(variant, intent, obj, item, base)
        answer = _answer_payload(role_id, intent, obj, item, base)
        qa_id = _qa_id(role_id, question, answer)
        records.append(
            SyntheticRoleQaRecord(
                record_type="role_qa",
                qa_id=qa_id,
                role_id=role_id,
                role_label=role_label,
                question=question,
                answer=answer,
                answer_state="seeded",
                tags=_tags(role_id, intent, obj, item),
                origin={
                    "kind": "synthetic_seed",
                    "generator": "runtime.synthetic_role_kb",
                    "source_knowledge_record": _source_record_id(item),
                    "base_question_id": base.get("id"),
                },
                feedback={
                    "positive_count": 0,
                    "negative_count": 0,
                    "last_cases": [],
                    "promotion_ready": False,
                },
                source_template=str(base.get("id") or item.get("record_type") or "synthetic"),
                trust_level=str(policy.get("trust_level") or "synthetic_seed"),
                evidence_strength=str(policy.get("evidence_strength") or "synthetic"),
                policy=_record_policy(policy),
                created_at=created_at,
            )
        )
        index += 1
    return records


def _knowledge_items() -> list[dict[str, Any]]:
    rows = [row for row in load_all_knowledge_records() if dict(row).get("record_type") != "role_qa"]
    return rows or [{"record_type": "generic", "label": "generic Python project"}]


def _empty_corpus() -> dict[str, Any]:
    policy = load_synthetic_policy()
    created_at = datetime.now(timezone.utc).isoformat()
    return {
        "artifact_type": "SyntheticRoleQACorpus",
        "schema_version": "synthetic_role_qa.v1",
        "created_at": created_at,
        "records_per_role": 0,
        "role_count": len(load_role_definitions()),
        "record_count": 0,
        "policy": _record_policy(policy),
        "records": [],
    }


def _llm_generation_messages(
    role: dict[str, Any],
    count: int,
    *,
    index: int = 0,
    seen_questions: list[str] | None = None,
) -> list[dict[str, str]]:
    compact = {
        "role_id": role.get("role_id"),
        "label": role.get("label"),
        "consumes": role.get("consumes", []),
        "produces": role.get("produces", []),
        "questions": role.get("questions", [])[:8],
    }
    return [
        {
            "role": "system",
            "content": (
                "You generate low-trust candidate Q/A seed records for Cognitive OS KB. "
                "Return strict JSON only. Do not claim ground truth, verification, authority, "
                "or permission to mutate source/registry/KB. Answers must be advisory and evidence-bound."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "generate_role_qa_seed_records",
                    "record_count": count,
                    "record_index": index,
                    "role": compact,
                    "avoid_questions": seen_questions or [],
                    "required_json_shape": {
                        "records": [
                            {
                                "question": "natural language question in Russian or English",
                                "answer": {
                                    "status": "candidate",
                                    "answer_type": "role_advisory_template",
                                    "short_answer": "bounded advisory answer",
                                    "recommended_steps": ["step"],
                                    "required_evidence": ["evidence"],
                                    "stop_conditions": ["condition"],
                                    "confidence": "low",
                                    "limitations": ["synthetic seed answer; not ground truth"],
                                },
                                "tags": ["tag"],
                            }
                        ]
                    },
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def _harden_llm_answer(role_id: str, answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "candidate",
        "answer_type": str(answer.get("answer_type") or "role_advisory_template"),
        "role_id": role_id,
        "short_answer": str(answer.get("short_answer") or "")[:1200],
        "recommended_steps": _string_list(answer.get("recommended_steps"), limit=10),
        "required_evidence": _string_list(answer.get("required_evidence"), limit=8),
        "stop_conditions": _string_list(answer.get("stop_conditions"), limit=8),
        "confidence": "low",
        "limitations": sorted(
            set(
                [
                    *_string_list(answer.get("limitations"), limit=8),
                    "LLM-generated synthetic seed; not ground truth",
                    "must be checked against project evidence before use",
                    "cannot promote to KB without repeated confirmed cases and approval",
                ]
            )
        ),
    }


def _string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, list):
        rows = [str(item).strip() for item in value if str(item).strip()]
    elif value:
        rows = [str(value).strip()]
    else:
        rows = []
    return rows[:limit]


def _provider_interface_seed_records(*, policy: dict[str, Any], created_at: str) -> list[SyntheticRoleQaRecord]:
    questions = _provider_interface_questions()
    records: list[SyntheticRoleQaRecord] = []
    role_labels = {
        "project_analyzer": "Project Analyzer",
        "architect": "Architect",
    }
    for index, question in enumerate(questions):
        role_id = "project_analyzer" if index % 3 else "architect"
        answer = _provider_interface_answer(role_id)
        records.append(
            SyntheticRoleQaRecord(
                record_type="role_qa",
                qa_id=_qa_id(role_id, question, answer),
                role_id=role_id,
                role_label=role_labels[role_id],
                question=question,
                answer=answer,
                answer_state="seeded",
                tags=[
                    role_id,
                    "provider_interface_mapping",
                    "llm_provider",
                    "adapter_class",
                    "openai_compatible",
                    "native_adapter",
                    "source_evidence",
                ],
                origin={
                    "kind": "synthetic_seed",
                    "generator": "runtime.synthetic_role_kb",
                    "source_knowledge_record": None,
                    "base_question_id": "provider_interface_mapping",
                },
                feedback={
                    "positive_count": 0,
                    "negative_count": 0,
                    "last_cases": [],
                    "promotion_ready": False,
                },
                source_template="provider_interface_mapping",
                trust_level=str(policy.get("trust_level") or "synthetic_seed"),
                evidence_strength=str(policy.get("evidence_strength") or "synthetic"),
                policy=_record_policy(policy),
                created_at=created_at,
            )
        )
    return records


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


STOPWORDS = {
    "что",
    "как",
    "какие",
    "какой",
    "какую",
    "если",
    "для",
    "при",
    "или",
    "это",
    "есть",
    "нужно",
    "нужны",
    "нужен",
    "перед",
    "после",
    "через",
    "with",
    "what",
    "how",
    "the",
    "and",
    "for",
    "from",
    "that",
    "this",
}


def _tokens(text: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {token for token in normalized.split() if len(token) > 2 and token not in STOPWORDS}


def _query_coverage_score(query_tokens: set[str], row_tokens: set[str]) -> float:
    if not query_tokens or not row_tokens:
        return 0.0
    intersection = query_tokens & row_tokens
    if not intersection:
        return 0.0
    query_coverage = len(intersection) / len(query_tokens)
    precision = len(intersection) / len(row_tokens)
    return (query_coverage * 0.85) + (precision * 0.15)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
