"""Durable Level 4 goal sessions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .goal_intake import merge_clarification


class GoalSessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.sessions_dir = root / "artifacts" / "goals" / "sessions"
        self.reports_dir = root / "artifacts" / "goals" / "reports"

    def create(self, goal: str, *, root_input: dict[str, Any] | None = None) -> dict[str, Any]:
        session_id = _new_goal_id(goal)
        session = {
            "goal_id": session_id,
            "goal": goal,
            "root_input": root_input or {},
            "status": "created",
            "created_at": _now(),
            "updated_at": _now(),
            "clarifications": [],
            "events": [],
        }
        self.save(session)
        return session

    def load(self, goal_id: str) -> dict[str, Any]:
        return json.loads(self._session_path(goal_id).read_text(encoding="utf-8"))

    def save(self, session: dict[str, Any]) -> None:
        session["updated_at"] = _now()
        path = self._session_path(str(session["goal_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def append_event(self, session: dict[str, Any], event: str, payload: dict[str, Any]) -> None:
        session.setdefault("events", []).append({"timestamp": _now(), "event": event, **payload})
        self.save(session)

    def add_clarification(self, session: dict[str, Any], answer: str) -> None:
        session.setdefault("clarifications", []).append({"timestamp": _now(), "answer": answer})
        session["goal"] = f"{session['goal']}\nClarification: {answer}"
        session["effective_goal"] = merge_clarification(str(session.get("effective_goal") or session["goal"]), answer)
        self.append_event(session, "clarification_added", {"answer": answer, "effective_goal": session["effective_goal"]})

    def write_report(self, session: dict[str, Any], report: dict[str, Any]) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"{session['goal_id']}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _session_path(self, goal_id: str) -> Path:
        return self.sessions_dir / f"{goal_id}.json"


def _new_goal_id(goal: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(f"{stamp}:{goal}".encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"goal_{stamp}_{digest}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
