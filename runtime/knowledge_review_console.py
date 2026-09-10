"""Review-oriented summaries for staged KnowledgeCandidate artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_admission import grouped_candidate_report, load_kb_candidates


def build_knowledge_review_console(*, root: Path) -> dict[str, Any]:
    candidates = load_kb_candidates(root=root)
    grouped = grouped_candidate_report(candidates)
    queues = {
        "ready_for_human_merge": [],
        "needs_teacher_approval": [],
        "needs_codex_approval": [],
        "collect_more_cases": [],
    }
    for group in grouped["groups"]:
        status = str(group.get("gate_status") or "collect_more_cases")
        row = _review_row(group)
        queues.setdefault(status, []).append(row)
    return {
        "artifact_type": "KnowledgeReviewConsole",
        "status": "ok",
        "candidate_count": len(candidates),
        "group_count": grouped["group_count"],
        "queues": queues,
        "next_actions": _next_actions(queues),
        "policy": grouped["policy"],
    }


def _review_row(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "group_key": group.get("group_key"),
        "record_type": group.get("record_type"),
        "proposed_id": group.get("proposed_id"),
        "label": group.get("label"),
        "confirmed_case_count": group.get("confirmed_case_count"),
        "reason": group.get("reason"),
        "candidate_ids": group.get("candidate_ids", []),
    }


def _next_actions(queues: dict[str, list[dict[str, Any]]]) -> list[str]:
    actions = []
    if queues.get("ready_for_human_merge"):
        actions.append("review ready_for_human_merge groups and merge manually if accepted")
    if queues.get("needs_teacher_approval"):
        actions.append("ask external teacher/corrector to approve or reject grouped candidates")
    if queues.get("needs_codex_approval"):
        actions.append("perform Codex/developer review for candidates already approved by teacher")
    if queues.get("collect_more_cases"):
        actions.append("run more verified cases before requesting approval")
    return actions or ["no staged knowledge candidates require action"]
