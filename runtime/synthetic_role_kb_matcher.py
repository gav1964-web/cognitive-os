from __future__ import annotations

import json
from typing import Any

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
    "быть",
    "были",
    "где",
    "его",
    "еще",
    "мне",
    "надо",
    "она",
    "они",
    "оно",
    "под",
    "почему",
    "чтобы",
    "делать",
    "are",
    "can",
    "does",
    "into",
    "must",
    "need",
    "needs",
    "not",
    "should",
    "use",
    "uses",
}

TOKEN_ALIASES = {
    "acceptance": {"acceptance", "criteria", "критерии", "приемка"},
    "adapter": {"adapter", "adapters", "адаптер", "адаптеры", "adapter_class"},
    "api": {"api", "интерфейс", "interface"},
    "contract": {"contract", "contracts", "контракт", "контракты"},
    "criteria": {"criteria", "критерии", "acceptance"},
    "evidence": {"evidence", "доказательства", "факты"},
    "external": {"external", "official", "source", "внешний", "источник"},
    "interface": {"interface", "интерфейс", "api"},
    "information": {"information", "knowledge", "evidence", "информация", "информации", "данные"},
    "kb": {"kb", "knowledge", "знание", "знания"},
    "llm": {"llm", "model", "models", "модель", "модели"},
    "merge": {"merge", "release", "релиз"},
    "openai": {"openai", "openaiadapter", "asyncopenai"},
    "provider": {"provider", "providers", "провайдер", "провайдеры"},
    "risk": {"risk", "risks", "риск", "риски"},
    "source": {"source", "источник", "исходник"},
    "technicalspec": {"technicalspec", "technical", "spec", "тз"},
    "tests": {"tests", "test", "тест", "тесты"},
    "тз": {"тз", "technicalspec", "technical", "spec", "specification"},
    "внешний": {"external", "official", "source", "источник"},
    "информации": {"information", "knowledge", "evidence", "gap"},
    "источник": {"source", "external", "official", "evidence"},
    "хватает": {"missing", "gap", "knowledge_gap", "evidence"},
}


def _tokens(text: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    tokens = {
        token
        for token in normalized.split()
        if token not in STOPWORDS and (len(token) > 2 or token in TOKEN_ALIASES)
    }
    expanded = set(tokens)
    for token in tokens:
        expanded.update(TOKEN_ALIASES.get(token, set()))
    return expanded


def _record_tokens(record: dict[str, Any]) -> set[str]:
    fields = _token_aware_fields(record)
    tokens: set[str] = set()
    for text in fields.values():
        tokens.update(_tokens(text))
    return tokens


def _token_aware_match_score(query_tokens: set[str], record: dict[str, Any]) -> dict[str, Any]:
    if not query_tokens:
        return {"score": 0.0, "details": {"matched_tokens": [], "field_matches": {}}}
    fields = _token_aware_fields(record)
    field_weights = {
        "question": 1.0,
        "tags": 0.85,
        "answer_short": 0.7,
        "answer_steps": 0.45,
        "answer_evidence": 0.65,
        "answer_shape": 0.6,
    }
    matched_tokens: set[str] = set()
    field_matches: dict[str, list[str]] = {}
    weighted_hits = 0.0
    weighted_possible = sum(field_weights.values())
    all_row_tokens: set[str] = set()
    for field, text in fields.items():
        row_tokens = _tokens(text)
        all_row_tokens.update(row_tokens)
        matched = sorted(query_tokens & row_tokens)
        if not matched:
            continue
        matched_tokens.update(matched)
        field_matches[field] = matched[:12]
        weighted_hits += field_weights.get(field, 0.35) * (len(matched) / max(1, len(query_tokens)))
    if not matched_tokens:
        return {"score": 0.0, "details": {"matched_tokens": [], "field_matches": {}}}
    query_coverage = len(matched_tokens) / len(query_tokens)
    precision = len(matched_tokens) / max(1, len(all_row_tokens))
    field_signal = min(1.0, weighted_hits / max(0.01, weighted_possible))
    score = (query_coverage * 0.72) + (field_signal * 0.2) + (precision * 0.08)
    return {
        "score": min(1.0, score),
        "details": {
            "matched_tokens": sorted(matched_tokens),
            "field_matches": field_matches,
            "query_coverage": round(query_coverage, 4),
            "field_signal": round(field_signal, 4),
            "precision": round(precision, 4),
        },
    }


def _token_aware_fields(record: dict[str, Any]) -> dict[str, str]:
    answer = dict(record.get("answer") or {})
    return {
        "question": str(record.get("question") or ""),
        "tags": " ".join(str(tag) for tag in record.get("tags", []) if tag),
        "answer_short": str(answer.get("short_answer") or ""),
        "answer_steps": " ".join(str(item) for item in answer.get("recommended_steps", []) if item),
        "answer_evidence": " ".join(str(item) for item in answer.get("required_evidence", []) if item),
        "answer_shape": json.dumps(answer.get("expected_output_shape") or {}, ensure_ascii=False, sort_keys=True),
    }


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
