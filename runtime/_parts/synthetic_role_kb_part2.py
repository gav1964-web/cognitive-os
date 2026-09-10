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

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "synthetic_role_kb_policy.json"
DEFAULT_CORPUS_PATH = ROOT / "artifacts" / "synthetic_kb_seed" / "synthetic_role_qa.json"
DEFAULT_KB_CORPUS_PATH = ROOT / "knowledge" / "role_qa" / "synthetic_role_qa.json"
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

def synthetic_role_qa_audit(corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    corpus = corpus or load_synthetic_role_qa()
    records = [dict(row) for row in corpus.get("records", []) if isinstance(row, dict)]
    qa_ids = [str(row.get("qa_id") or "") for row in records if row.get("qa_id")]
    duplicate_ids = sorted([qa_id for qa_id, count in Counter(qa_ids).items() if count > 1])
    missing_fields = []
    invalid_policy = []
    empty_token_records = []
    token_counts = []
    for row in records:
        qa_id = str(row.get("qa_id") or "<missing>")
        missing = [field for field in ("qa_id", "role_id", "question", "answer", "policy", "trust_level") if not row.get(field)]
        if missing:
            missing_fields.append({"qa_id": qa_id, "missing": missing})
        policy = dict(row.get("policy") or {})
        if policy.get("auto_promote") is not False or policy.get("authority") != "advisory_only":
            invalid_policy.append(qa_id)
        tokens = _record_tokens(row)
        token_counts.append(len(tokens))
        if not tokens:
            empty_token_records.append(qa_id)
    probe = synthetic_probe_report(corpus)
    weak_probes = [row for row in probe["rows"] if row["quality"] in {"weak", "miss"}]
    avg_tokens = round(sum(token_counts) / max(1, len(token_counts)), 2)
    status = "ok"
    if duplicate_ids or missing_fields or invalid_policy or empty_token_records or weak_probes:
        status = "needs_review"
    return {
        "artifact_type": "SyntheticRoleQAAudit",
        "schema_version": "synthetic_role_qa_audit.v1",
        "status": status,
        "record_count": len(records),
        "role_count": len({str(row.get("role_id")) for row in records if row.get("role_id")}),
        "average_record_token_count": avg_tokens,
        "duplicate_qa_ids": duplicate_ids[:20],
        "duplicate_qa_id_count": len(duplicate_ids),
        "missing_field_count": len(missing_fields),
        "missing_fields": missing_fields[:20],
        "invalid_policy_count": len(invalid_policy),
        "invalid_policy_qa_ids": invalid_policy[:20],
        "empty_token_record_count": len(empty_token_records),
        "empty_token_qa_ids": empty_token_records[:20],
        "probe_report": probe,
        "weak_probe_count": len(weak_probes),
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
