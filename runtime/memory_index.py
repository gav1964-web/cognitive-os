"""Goal memory index over completed Level 4 reports."""

from __future__ import annotations

import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryIndex:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "artifacts" / "memory" / "memory_index.json"
        self.reports_dir = root / "artifacts" / "goals" / "reports"

    def rebuild(self) -> dict[str, Any]:
        entries = []
        for report_path in sorted(self.reports_dir.glob("*.json")):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            entries.append(_entry_from_report(report, report_path))
        payload = {"updated_at": _now(), "entries": entries, "templates": _build_templates(entries)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload

    def upsert_report(self, report: dict[str, Any], report_path: Path) -> dict[str, Any]:
        payload = self.load()
        entry = _entry_from_report(report, report_path)
        entries = [item for item in payload.get("entries", []) if item.get("goal_id") != entry["goal_id"]]
        entries.append(entry)
        entries = sorted(entries, key=lambda item: str(item["goal_id"]))
        payload = {"updated_at": _now(), "entries": entries, "templates": _build_templates(entries)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return entry

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"updated_at": None, "entries": [], "templates": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        query_tokens = _tokens(query)
        payload = self.load()
        matches = []
        for entry in payload.get("entries", []):
            entry_tokens = set(entry.get("tokens", []))
            score = _jaccard(query_tokens, entry_tokens)
            if score <= 0:
                continue
            matches.append({"score": score, **entry})
        matches.sort(key=lambda item: (-float(item["score"]), str(item["goal_id"])))
        template_matches = []
        for template in payload.get("templates", []):
            template_tokens = set(template.get("tokens", []))
            score = _jaccard(query_tokens, template_tokens)
            if score <= 0:
                continue
            template_matches.append({"score": score, **template})
        template_matches.sort(key=lambda item: (-float(item["score"]), -int(item["support_count"]), str(item["template_id"])))
        recommendation = _recommendation(matches)
        template_recommendation = _template_recommendation(template_matches)
        return {
            "query": query,
            "matches": matches[:limit],
            "recommendation": recommendation,
            "template_matches": template_matches[:limit],
            "template_recommendation": template_recommendation,
        }


def _entry_from_report(report: dict[str, Any], report_path: Path) -> dict[str, Any]:
    goal = str(report.get("goal", ""))
    execution = dict(report.get("execution", {}))
    plan = dict(report.get("level35_plan", {}))
    pipeline = dict(plan.get("pipeline", {}))
    nodes = list(pipeline.get("nodes", []))
    return {
        "goal_id": report.get("goal_id"),
        "goal": goal,
        "summary": report.get("summary"),
        "status": report.get("status"),
        "decision_action": dict(report.get("level4_decision", {})).get("action"),
        "execution_status": execution.get("status"),
        "completed_nodes": execution.get("completed_nodes", []),
        "pipeline_id": pipeline.get("id"),
        "capabilities": [node.get("capability") for node in nodes],
        "pipeline_template": {
            "nodes": [
                {
                    "id": node.get("id"),
                    "capability": node.get("capability"),
                    "input": node.get("input", {}),
                }
                for node in nodes
            ],
            "edges": pipeline.get("edges", []),
            "retry_policy": pipeline.get("retry_policy", {}),
        },
        "report_path": report_path.as_posix(),
        "tokens": sorted(_tokens(goal)),
    }


def _recommendation(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not matches:
        return None
    best = matches[0]
    if float(best["score"]) < 0.25:
        return None
    if best.get("execution_status") == "ok" and best.get("capabilities"):
        return {
            "action": "CONSIDER_REUSE_PREVIOUS_PLAN",
            "goal_id": best.get("goal_id"),
            "pipeline_id": best.get("pipeline_id"),
            "capabilities": best.get("capabilities"),
            "score": best.get("score"),
        }
    return {
        "action": "REVIEW_SIMILAR_GOAL",
        "goal_id": best.get("goal_id"),
        "score": best.get("score"),
    }


def _template_recommendation(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [match for match in matches if match.get("safety_status") == "mature"]
    if not matches:
        return None
    best = matches[0]
    if float(best["score"]) < 0.25:
        return None
    return {
        "action": "CONSIDER_REUSE_PLAN_TEMPLATE",
        "template_id": best.get("template_id"),
        "capabilities": best.get("capabilities"),
        "support_count": best.get("support_count"),
        "safety_status": best.get("safety_status"),
        "score": best.get("score"),
    }


def _build_templates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if not entry.get("capabilities") or not dict(entry.get("pipeline_template", {})).get("nodes"):
            continue
        key = _template_key(entry)
        grouped.setdefault(key, []).append(entry)
    templates = []
    for key, group in grouped.items():
        successes = [entry for entry in group if entry.get("execution_status") == "ok"]
        failures = [entry for entry in group if entry.get("execution_status") not in {None, "ok"}]
        if not successes:
            continue
        first = successes[0]
        tokens = set()
        for entry in successes:
            tokens.update(entry.get("tokens", []))
        safety_status = _template_safety_status(success_count=len(successes), failure_count=len(failures))
        templates.append(
            {
                "template_id": f"tpl_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}",
                "capabilities": first.get("capabilities", []),
                "support_count": len(successes),
                "success_count": len(successes),
                "failure_count": len(failures),
                "safety_status": safety_status,
                "goal_ids": [entry.get("goal_id") for entry in successes],
                "failure_goal_ids": [entry.get("goal_id") for entry in failures],
                "example_goal": first.get("goal"),
                "pipeline_template": first.get("pipeline_template", {}),
                "tokens": sorted(tokens),
            }
        )
    return sorted(templates, key=lambda item: (-int(item["support_count"]), str(item["template_id"])))


def _template_key(entry: dict[str, Any]) -> str:
    template = dict(entry.get("pipeline_template", {}))
    shape = {
        "capabilities": entry.get("capabilities", []),
        "inputs": [dict(node).get("input", {}) for node in template.get("nodes", [])],
        "edges": template.get("edges", []),
    }
    return json.dumps(shape, ensure_ascii=False, sort_keys=True)


def _template_safety_status(*, success_count: int, failure_count: int) -> str:
    if failure_count > 0:
        return "blocked_by_failures"
    if success_count < 2:
        return "immature"
    return "mature"


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "then", "from", "with", "into", "this", "that", "input", "output"}
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if token not in stop and len(token) > 2}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
