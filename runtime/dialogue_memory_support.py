"""Small pure helpers for dialogue memory."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


NOTE_KINDS = {"note", "decision", "open_thread", "principle", "preference"}


def recall_recommendation(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not matches or float(matches[0]["score"]) < 0.2:
        return None
    best = matches[0]
    return {
        "action": "CONSIDER_DIALOGUE_CONTEXT",
        "record_id": best.get("record_id"),
        "kind": best.get("kind"),
        "topic": best.get("topic"),
        "score": best.get("score"),
    }


def compact_text(topic: str, turns: list[dict[str, Any]]) -> str:
    all_text = " ".join(str(turn.get("content", "")) for turn in turns)
    keywords = top_tokens(tokens(all_text), limit=8)
    roles = sorted({str(turn.get("role")) for turn in turns if turn.get("role")})
    first = snippet(str(turns[0].get("content", "")))
    last = snippet(str(turns[-1].get("content", "")))
    return (
        f"Topic: {topic}. Turns: {len(turns)}. Roles: {', '.join(roles)}. "
        f"Keywords: {', '.join(keywords)}. First: {first}. Last: {last}."
    )


def related_topics(graph: dict[str, Any], topic: str, *, limit: int) -> list[dict[str, Any]]:
    related = []
    for edge in graph.get("edges", []):
        if edge.get("source") == topic:
            related.append({"topic": edge.get("target"), "score": edge.get("score"), "shared_tokens": edge.get("shared_tokens", [])})
        elif edge.get("target") == topic:
            related.append({"topic": edge.get("source"), "score": edge.get("score"), "shared_tokens": edge.get("shared_tokens", [])})
    related.sort(key=lambda item: (-float(item["score"]), str(item["topic"])))
    return related[:limit]


def top_tokens(value: set[str], *, limit: int) -> list[str]:
    return sorted(value)[:limit]


def snippet(text: str, *, max_len: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def tokens(text: str) -> set[str]:
    stop = {"the", "and", "then", "from", "with", "into", "this", "that", "input", "output"}
    return {token for token in re.findall(r"[a-zA-Zа-яА-Я0-9_]+", text.lower()) if token not in stop and len(token) > 2}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def new_dialogue_id(seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(f"{stamp}:{seed}".encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"dlg_{stamp}_{digest}"


def new_record_id(kind: str, text: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(f"{stamp}:{kind}:{text}".encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{kind}_{stamp}_{digest}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
