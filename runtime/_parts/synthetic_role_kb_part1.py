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

class SyntheticRoleKbError(RuntimeError):
    """Raised when synthetic KB input or policy is invalid."""

@dataclass
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
