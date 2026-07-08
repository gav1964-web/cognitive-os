"""Durable dialogue memory for human conversation context.

Dialogue memory is contextual. It does not build pipelines, mutate registry
state, or execute capabilities.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .dialogue_memory_support import (
    NOTE_KINDS,
    compact_text,
    jaccard,
    new_dialogue_id,
    new_record_id,
    now,
    recall_recommendation,
    related_topics,
    tokens,
)


class DialogueMemory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.base_dir = root / "artifacts" / "dialogue"
        self.sessions_dir = self.base_dir / "sessions"
        self.topics_path = self.base_dir / "topics.json"
        self.decisions_path = self.base_dir / "decisions.json"
        self.open_threads_path = self.base_dir / "open_threads.json"
        self.principles_path = self.base_dir / "principles.json"
        self.summaries_path = self.base_dir / "summaries.json"
        self.topic_graph_path = self.base_dir / "topic_graph.json"

    def create_session(self, *, title: str = "", topic: str = "default") -> dict[str, Any]:
        dialogue_id = new_dialogue_id(title or topic)
        session = {
            "dialogue_id": dialogue_id,
            "title": title,
            "active_topic": topic,
            "created_at": now(),
            "updated_at": now(),
            "turns": [],
        }
        self.save_session(session)
        self._touch_topic(topic, dialogue_id=dialogue_id)
        return session

    def load_session(self, dialogue_id: str) -> dict[str, Any]:
        return json.loads((self.sessions_dir / f"{dialogue_id}.json").read_text(encoding="utf-8"))

    def save_session(self, session: dict[str, Any]) -> None:
        session["updated_at"] = now()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self.sessions_dir / f"{session['dialogue_id']}.json"
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def add_turn(self, dialogue_id: str, *, role: str, content: str, topic: str | None = None) -> dict[str, Any]:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"unsupported dialogue role: {role}")
        session = self.load_session(dialogue_id)
        active_topic = topic or str(session.get("active_topic") or "default")
        turn = {
            "turn_id": new_record_id("turn", content),
            "timestamp": now(),
            "role": role,
            "topic": active_topic,
            "content": content,
            "tokens": sorted(tokens(content)),
        }
        session.setdefault("turns", []).append(turn)
        session["active_topic"] = active_topic
        self.save_session(session)
        self._touch_topic(active_topic, dialogue_id=dialogue_id)
        return turn

    def switch_topic(self, dialogue_id: str, topic: str) -> dict[str, Any]:
        session = self.load_session(dialogue_id)
        previous = session.get("active_topic")
        session["active_topic"] = topic
        self.save_session(session)
        self._touch_topic(topic, dialogue_id=dialogue_id)
        return {"dialogue_id": dialogue_id, "previous_topic": previous, "active_topic": topic}

    def note(
        self,
        *,
        text: str,
        kind: str = "note",
        topic: str = "default",
        dialogue_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if kind not in NOTE_KINDS:
            raise ValueError(f"unsupported dialogue note kind: {kind}")
        record = {
            "record_id": new_record_id(kind, text),
            "timestamp": now(),
            "kind": kind,
            "topic": topic,
            "dialogue_id": dialogue_id,
            "text": text,
            "tags": tags or [],
            "tokens": sorted(tokens(text) | tokens(topic) | set(tags or [])),
        }
        if kind == "decision":
            self._append_collection(self.decisions_path, record)
        elif kind == "open_thread":
            self._append_collection(self.open_threads_path, record)
        elif kind in {"principle", "preference"}:
            self._append_collection(self.principles_path, record)
        self._touch_topic(topic, dialogue_id=dialogue_id, note=record)
        return record

    def recall(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        query_tokens = tokens(query)
        candidates = []
        for record in self._all_records():
            score = jaccard(query_tokens, set(record.get("tokens", [])))
            if score > 0:
                candidates.append({"score": score, **record})
        candidates.sort(key=lambda item: (-float(item["score"]), str(item.get("timestamp", ""))))
        return {
            "query": query,
            "matches": candidates[:limit],
            "recommendation": recall_recommendation(candidates),
        }

    def summary(self, *, dialogue_id: str | None = None, topic: str | None = None, limit: int = 10) -> dict[str, Any]:
        topics = self._load_json(self.topics_path, default={"topics": {}}).get("topics", {})
        session = self.load_session(dialogue_id) if dialogue_id else None
        active_topic = topic or (str(session.get("active_topic")) if session else None)
        turns = list(session.get("turns", []))[-limit:] if session else []
        compact_summaries = self._filter_records(
            self._load_collection(self.summaries_path),
            topic=active_topic,
            dialogue_id=dialogue_id,
            limit=limit,
        )
        graph = self.load_topic_graph()
        return {
            "dialogue_id": dialogue_id,
            "active_topic": active_topic,
            "topic": topics.get(active_topic, {}) if active_topic else None,
            "recent_turns": turns,
            "compact_summaries": compact_summaries,
            "related_topics": related_topics(graph, active_topic, limit=5) if active_topic else [],
            "decisions": self._filter_records(self._load_collection(self.decisions_path), topic=active_topic, limit=limit),
            "open_threads": self._filter_records(self._load_collection(self.open_threads_path), topic=active_topic, limit=limit),
            "principles": self._filter_records(self._load_collection(self.principles_path), topic=active_topic, limit=limit),
        }

    def compact_session(self, dialogue_id: str, *, keep_recent_turns: int = 8) -> dict[str, Any]:
        session = self.load_session(dialogue_id)
        turns = list(session.get("turns", []))
        if not turns:
            raise ValueError(f"dialogue session has no turns: {dialogue_id}")
        active_topic = str(session.get("active_topic") or "default")
        archived_turns = turns[:-keep_recent_turns] if keep_recent_turns > 0 else turns
        if not archived_turns:
            archived_turns = turns
        record = {
            "record_id": new_record_id("summary", dialogue_id),
            "timestamp": now(),
            "kind": "summary",
            "topic": active_topic,
            "dialogue_id": dialogue_id,
            "turn_count": len(archived_turns),
            "source_turn_ids": [turn.get("turn_id") for turn in archived_turns],
            "text": compact_text(active_topic, archived_turns),
            "tokens": sorted(tokens(" ".join(str(turn.get("content", "")) for turn in archived_turns)) | tokens(active_topic)),
        }
        self._append_collection(self.summaries_path, record)
        session.setdefault("compactions", []).append(
            {
                "timestamp": record["timestamp"],
                "summary_id": record["record_id"],
                "source_turn_count": len(archived_turns),
                "kept_recent_turns": min(len(turns), keep_recent_turns),
            }
        )
        self.save_session(session)
        self.rebuild_topic_graph()
        return record

    def rebuild_topic_graph(self) -> dict[str, Any]:
        topics = self._load_json(self.topics_path, default={"topics": {}}).get("topics", {})
        topic_tokens: dict[str, set[str]] = {topic: tokens(topic) for topic in topics}
        for record in self._all_records():
            topic = record.get("topic")
            if not topic:
                continue
            topic_tokens.setdefault(str(topic), set()).update(set(record.get("tokens", [])))
        nodes = [
            {
                "topic": topic,
                "tokens": sorted(tokens),
                "dialogue_ids": topics.get(topic, {}).get("dialogue_ids", []),
                "note_count": topics.get(topic, {}).get("note_count", 0),
            }
            for topic, tokens in sorted(topic_tokens.items())
        ]
        edges = []
        names = sorted(topic_tokens)
        for index, left in enumerate(names):
            for right in names[index + 1 :]:
                score = jaccard(topic_tokens[left], topic_tokens[right])
                if score <= 0:
                    continue
                edges.append(
                    {
                        "source": left,
                        "target": right,
                        "score": score,
                        "shared_tokens": sorted(topic_tokens[left] & topic_tokens[right]),
                    }
                )
        edges.sort(key=lambda item: (-float(item["score"]), str(item["source"]), str(item["target"])))
        merge_suggestions = [
            {
                "source": edge["source"],
                "target": edge["target"],
                "score": edge["score"],
                "reason": "high_token_overlap",
            }
            for edge in edges
            if float(edge["score"]) >= 0.5
        ]
        payload = {"updated_at": now(), "nodes": nodes, "edges": edges, "merge_suggestions": merge_suggestions}
        self._write_json(self.topic_graph_path, payload)
        return payload

    def load_topic_graph(self) -> dict[str, Any]:
        if not self.topic_graph_path.exists():
            return self.rebuild_topic_graph()
        return self._load_json(self.topic_graph_path, default={"updated_at": None, "nodes": [], "edges": [], "merge_suggestions": []})

    def _touch_topic(
        self,
        topic: str,
        *,
        dialogue_id: str | None = None,
        note: dict[str, Any] | None = None,
    ) -> None:
        payload = self._load_json(self.topics_path, default={"topics": {}})
        topics = payload.setdefault("topics", {})
        row = topics.setdefault(
            topic,
            {
                "topic": topic,
                "created_at": now(),
                "updated_at": now(),
                "dialogue_ids": [],
                "note_count": 0,
                "decision_count": 0,
                "open_thread_count": 0,
                "principle_count": 0,
            },
        )
        row["updated_at"] = now()
        if dialogue_id and dialogue_id not in row.setdefault("dialogue_ids", []):
            row["dialogue_ids"].append(dialogue_id)
        if note:
            row["note_count"] = int(row.get("note_count", 0)) + 1
            if note["kind"] == "decision":
                row["decision_count"] = int(row.get("decision_count", 0)) + 1
            elif note["kind"] == "open_thread":
                row["open_thread_count"] = int(row.get("open_thread_count", 0)) + 1
            elif note["kind"] in {"principle", "preference"}:
                row["principle_count"] = int(row.get("principle_count", 0)) + 1
        self._write_json(self.topics_path, payload)
        self.rebuild_topic_graph()

    def _all_records(self) -> list[dict[str, Any]]:
        records = []
        records.extend(self._load_collection(self.decisions_path))
        records.extend(self._load_collection(self.open_threads_path))
        records.extend(self._load_collection(self.principles_path))
        records.extend(self._load_collection(self.summaries_path))
        topics = self._load_json(self.topics_path, default={"topics": {}}).get("topics", {})
        for topic, row in topics.items():
            records.append(
                {
                    "record_id": f"topic_{hashlib.sha256(str(topic).encode('utf-8')).hexdigest()[:12]}",
                    "timestamp": row.get("updated_at"),
                    "kind": "topic",
                    "topic": topic,
                    "text": topic,
                    "tokens": sorted(tokens(topic)),
                }
            )
        for path in sorted(self.sessions_dir.glob("*.json")):
            session = json.loads(path.read_text(encoding="utf-8"))
            for turn in session.get("turns", []):
                records.append(
                    {
                        "record_id": turn.get("turn_id"),
                        "timestamp": turn.get("timestamp"),
                        "kind": "turn",
                        "topic": turn.get("topic"),
                        "dialogue_id": session.get("dialogue_id"),
                        "role": turn.get("role"),
                        "text": turn.get("content"),
                        "tokens": turn.get("tokens", []),
                    }
                )
        return records

    def _append_collection(self, path: Path, record: dict[str, Any]) -> None:
        payload = self._load_json(path, default={"records": []})
        records = [item for item in payload.get("records", []) if item.get("record_id") != record["record_id"]]
        records.append(record)
        payload = {"updated_at": now(), "records": sorted(records, key=lambda item: str(item["record_id"]))}
        self._write_json(path, payload)

    def _load_collection(self, path: Path) -> list[dict[str, Any]]:
        return list(self._load_json(path, default={"records": []}).get("records", []))

    def _filter_records(
        self,
        records: list[dict[str, Any]],
        *,
        topic: str | None,
        dialogue_id: str | None = None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if topic:
            records = [record for record in records if record.get("topic") == topic]
        if dialogue_id:
            records = [record for record in records if record.get("dialogue_id") == dialogue_id]
        return sorted(records, key=lambda item: str(item.get("timestamp", "")), reverse=True)[:limit]

    def _load_json(self, path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
