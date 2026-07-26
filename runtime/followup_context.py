"""Resolve short follow-up prompts from recent verified goal reports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .capability_routes import match_capability_route_row
from .followup_rules import markers


def resolve_followup_goal(root: Path, goal: str, root_input: dict[str, Any]) -> dict[str, Any] | None:
    replacement = _replacement_request(goal)
    if replacement is None:
        return _resolve_project_followup(root, goal, root_input)
    prior = _latest_client_port_answer(root)
    if prior is None:
        return None
    old_value = str(prior["port"])
    new_value = replacement
    target = str(prior["target"])
    paths = [str(item.get("path")) for item in prior.get("evidence", []) if item.get("path")]
    return {
        "effective_goal": f"По проекту {target} замени порт подключения клиентов {old_value} на {new_value}",
        "root_input": {
            **root_input,
            "path": target,
            "old_value": old_value,
            "new_value": new_value,
            "candidate_paths": _dedupe(paths),
            "max_replacements": 20,
        },
        "source": "recent_project_fact_question",
        "resolved_reference": {
            "kind": "client_connection_port",
            "old_value": old_value,
            "new_value": new_value,
            "target": target,
            "candidate_paths": _dedupe(paths),
        },
    }


def _resolve_project_followup(root: Path, goal: str, root_input: dict[str, Any]) -> dict[str, Any] | None:
    if root_input.get("path") or root_input.get("project_path"):
        return None
    if not (_looks_like_question(goal) or _looks_like_project_change(goal)):
        return None
    prior = _latest_project_context(root)
    if prior is None:
        return None
    target = str(prior["target"])
    if _looks_like_question(goal):
        return {
            "effective_goal": f"По проекту {target} ответь на вопрос: {goal}",
            "root_input": {
                **root_input,
                "path": target,
                "question": goal,
            },
            "source": "recent_project_context",
            "resolved_reference": {
                "kind": "project_fact_question",
                "target": target,
                "question": goal,
                "report_path": prior.get("report_path"),
            },
        }
    route = match_capability_route_row(goal) or {}
    return {
        "effective_goal": f"По проекту {target} выполни изменение: {goal}",
        "root_input": {
            **root_input,
            "path": target,
            **dict(route.get("input_defaults") or {}),
        },
        "source": "recent_project_context",
        "resolved_reference": {
            "kind": "project_change",
            "target": target,
            "goal": goal,
            "report_path": prior.get("report_path"),
        },
    }


def _looks_like_question(goal: str) -> bool:
    lowered = " ".join(goal.lower().strip().split())
    return lowered.endswith("?") or any(token in lowered for token in markers("question_markers"))


def _looks_like_project_change(goal: str) -> bool:
    lowered = " ".join(goal.lower().strip().split())
    return any(token in lowered for token in markers("change_markers"))


def _latest_project_context(root: Path) -> dict[str, Any] | None:
    reports_dir = root / "artifacts" / "goals" / "reports"
    for path in sorted(reports_dir.glob("goal_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        target = dict(report.get("goal_intake") or {}).get("target")
        if target:
            return {"target": target, "report_path": path.as_posix()}
    return None


def _replacement_request(goal: str) -> str | None:
    lowered = " ".join(goal.lower().strip().split())
    if not any(token in lowered for token in markers("replacement_action_markers")):
        return None
    if not any(token in lowered for token in markers("replacement_reference_markers")):
        return None
    match = re.search(r"(?:на|to)\s+([0-9]{2,5})\b", lowered)
    return match.group(1) if match else None


def _latest_client_port_answer(root: Path) -> dict[str, Any] | None:
    reports_dir = root / "artifacts" / "goals" / "reports"
    for path in sorted(reports_dir.glob("goal_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        answer = (
            dict(report.get("execution") or {})
            .get("outputs", {})
            .get("project_fact_questions", {})
            .get("answers", {})
            .get("client_connection_port")
        )
        if not isinstance(answer, dict) or answer.get("status") != "found" or answer.get("port") is None:
            continue
        target = dict(report.get("goal_intake") or {}).get("target")
        if not target:
            continue
        return {
            "target": target,
            "port": answer["port"],
            "evidence": list(answer.get("evidence") or []),
            "report_path": path.as_posix(),
        }
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
