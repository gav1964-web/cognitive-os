"""Convert project-analysis signals into actionable follow-up tasks."""

from __future__ import annotations

import hashlib
from typing import Any


TASK_TYPES = {
    "MAP_SUBSYSTEM_BOUNDARY",
    "CLARIFY_OWNERSHIP_BOUNDARY",
    "EXTRACT_CAPABILITY",
    "HARDEN_CONTRACT",
    "DESIGN_RECOVERY_LOOP",
    "REFINE_ARCHITECTURE_HOTSPOT",
    "ANSWER_OPEN_QUESTION",
    "REVIEW_HUMAN_DECISION",
    "SPLIT_MIXED_RESPONSIBILITY",
    "MAKE_ORCHESTRATION_EXPLICIT",
    "ADD_IDEMPOTENCY_GUARD",
    "DEFINE_QUARANTINE_POLICY",
    "ISOLATE_PROCESS_BOUNDARY",
    "DEFINE_CHECKPOINT_POLICY",
    "DRAFT_PIPELINE_CAPABILITY",
}

PRIORITY_BY_SEVERITY = {"high": "P1", "medium": "P2", "low": "P3"}


def generate_project_tasks(
    *,
    level35_signals: dict[str, Any],
    level4_interpretation: dict[str, Any],
    limit: int = 20,
) -> dict[str, Any]:
    """Build deterministic task candidates from machine impulses and L4 prose."""

    tasks: list[dict[str, Any]] = []
    for signal in _signals(level35_signals):
        task = _task_from_signal(signal)
        if task:
            tasks.append(task)
    for index, item in enumerate(_short_list(level4_interpretation.get("refactor_plan"))):
        tasks.append(
            _task(
                task_type="REFINE_ARCHITECTURE_HOTSPOT",
                title=item,
                target=_target_from_text(item),
                priority="P2",
                source="L4.refactor_plan",
                evidence={"index": index, "text": item},
                acceptance="A reviewer can point to the changed boundary, contract, or function split.",
            )
        )
    for index, item in enumerate(_short_list(level4_interpretation.get("open_questions"))):
        tasks.append(
            _task(
                task_type="ANSWER_OPEN_QUESTION",
                title=item,
                target=_target_from_text(item),
                priority="P3",
                source="L4.open_questions",
                evidence={"index": index, "text": item},
                acceptance="The answer is recorded as a project fact, decision, or deferred risk.",
            )
        )
    merged = _dedupe(tasks)[:limit]
    return {
        "layer": "L4",
        "source": "deterministic_task_synthesizer",
        "task_count": len(merged),
        "tasks": merged,
    }


def _task_from_signal(signal: dict[str, Any]) -> dict[str, Any] | None:
    signal_type = str(signal.get("type") or "")
    target = str(signal.get("target") or "").strip()
    if not target:
        return None
    severity = str(signal.get("severity") or "medium").lower()
    priority = PRIORITY_BY_SEVERITY.get(severity, "P2")
    if signal_type == "SUBSYSTEM_HOTSPOT":
        return _task(
            task_type="MAP_SUBSYSTEM_BOUNDARY",
            title=f"Map subsystem boundary for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Subsystem inputs, outputs, owned files, and external dependencies are listed.",
        )
    if signal_type == "OWNERSHIP_BOUNDARY":
        return _task(
            task_type="CLARIFY_OWNERSHIP_BOUNDARY",
            title=f"Clarify ownership boundary for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Boundary owner, allowed callers, and forbidden coupling are documented.",
        )
    if signal_type == "MIXED_RESPONSIBILITY":
        return _task(
            task_type="SPLIT_MIXED_RESPONSIBILITY",
            title=f"Split mixed responsibilities in {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="I/O, decision logic, formatting, error handling, and side effects are separated or explicitly wrapped.",
        )
    if signal_type == "HIDDEN_ORCHESTRATOR":
        return _task(
            task_type="MAKE_ORCHESTRATION_EXPLICIT",
            title=f"Make hidden orchestration explicit in {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Control-flow node has named steps, inputs, outputs, and delegated capabilities.",
        )
    if signal_type == "IDEMPOTENCY_RISK":
        return _task(
            task_type="ADD_IDEMPOTENCY_GUARD",
            title=f"Add idempotency/replay guard for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Retry/replay behavior is protected by idempotency key, output existence check, or transaction boundary.",
        )
    if signal_type == "QUARANTINE_CANDIDATE":
        return _task(
            task_type="DEFINE_QUARANTINE_POLICY",
            title=f"Define on-demand quarantine policy for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Failure class, threshold, registry status change, and interrupt packet contents are specified.",
        )
    if signal_type == "PROCESS_BOUNDARY_CANDIDATE":
        return _task(
            task_type="ISOLATE_PROCESS_BOUNDARY",
            title=f"Isolate process boundary for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Execution policy includes timeout, captured stdout/stderr/artifacts, and kill/retry behavior.",
        )
    if signal_type == "CHECKPOINT_CANDIDATE":
        return _task(
            task_type="DEFINE_CHECKPOINT_POLICY",
            title=f"Define checkpoint/reuse policy for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Resume can distinguish reusable artifacts from steps that must be recomputed.",
        )
    if signal_type in {"BROAD_FUNCTION", "CAPABILITY_CANDIDATE"}:
        return _task(
            task_type="EXTRACT_CAPABILITY",
            title=f"Extract capability candidate from {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Candidate has one input contract, one output contract, and focused tests.",
        )
    if signal_type in {"WEAK_CONTRACT", "UNKNOWN_BOUNDARY"}:
        return _task(
            task_type="HARDEN_CONTRACT",
            title=f"Harden contract around {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Input/output schema or typed boundary exists and contract mismatch is testable.",
        )
    if signal_type == "MVP_EXTRACTION_CANDIDATE":
        return _task(
            task_type="DRAFT_PIPELINE_CAPABILITY",
            title=f"Draft first Pipeline DSL capability for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Capability candidate has a minimal input/output contract and can be placed into a first useful Pipeline DSL.",
        )
    if signal_type in {"PIPELINE_CANDIDATE", "RECOVERY_LOOP_CANDIDATE"}:
        return _task(
            task_type="DESIGN_RECOVERY_LOOP",
            title=f"Design Cognitive OS loop for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Pipeline, controlled failure, interrupt, retry/switch/stop, and final report are specified.",
        )
    if signal_type in {"ARCHITECTURE_HOTSPOT", "ENTRYPOINT_FOUND"}:
        return _task(
            task_type="REFINE_ARCHITECTURE_HOTSPOT",
            title=f"Refine architecture hotspot {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Hotspot role, callers, callees, and reduction path are explicit.",
        )
    if signal_type == "NEEDS_HUMAN_DECISION":
        return _task(
            task_type="REVIEW_HUMAN_DECISION",
            title=f"Review human decision for {target}",
            target=target,
            priority=priority,
            source="L3.5.signal",
            evidence=signal,
            acceptance="Human decision is captured as accepted, rejected, or deferred.",
        )
    return None


def _task(
    *,
    task_type: str,
    title: str,
    target: str,
    priority: str,
    source: str,
    evidence: dict[str, Any],
    acceptance: str,
) -> dict[str, Any]:
    if task_type not in TASK_TYPES:
        task_type = "REVIEW_HUMAN_DECISION"
    seed = f"{task_type}:{target}:{title}"
    return {
        "task_id": "analysis_" + hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12],
        "type": task_type,
        "title": title,
        "target": target,
        "priority": priority,
        "status": "proposed",
        "source": source,
        "evidence": evidence,
        "acceptance": acceptance,
    }


def _signals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("signals", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _short_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value[:3] if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _target_from_text(text: str) -> str:
    words = [word.strip(".,:;()[]{}") for word in text.split()]
    for word in words:
        if "/" in word or "\\" in word or ".py" in word or ":" in word:
            return word
    return "project"


def _dedupe(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for task in tasks:
        key = (task.get("type"), task.get("target"))
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    result.sort(key=lambda item: (priority_order.get(str(item.get("priority")), 9), str(item.get("type")), str(item.get("target"))))
    return result
