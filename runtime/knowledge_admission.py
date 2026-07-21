"""Admission gate for promoting external observations into the knowledge base."""

from __future__ import annotations

import hashlib
import json
from json import JSONDecodeError
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MIN_CONFIRMED_CASES = 3


@dataclass(frozen=True)
class KnowledgeCandidate:
    candidate_id: str
    record_type: str
    proposed_record: dict[str, Any]
    source_cases: list[dict[str, Any]]
    teacher_reference: str
    teacher_approved: bool
    codex_approved: bool
    evidence_policy: dict[str, Any]
    status: str
    reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_kb_candidate(
    *,
    record_type: str,
    proposed_record: dict[str, Any],
    source_cases: list[dict[str, Any]],
    teacher_reference: str,
    teacher_approved: bool = False,
    codex_approved: bool = False,
    min_confirmed_cases: int = MIN_CONFIRMED_CASES,
) -> dict[str, Any]:
    """Create a staged candidate; never promotes automatically."""

    confirmed = _confirmed_cases(source_cases)
    status, reason = _admission_status(
        confirmed_cases=len(confirmed),
        teacher_approved=teacher_approved,
        codex_approved=codex_approved,
        min_confirmed_cases=min_confirmed_cases,
    )
    candidate = KnowledgeCandidate(
        candidate_id=_candidate_id(record_type, proposed_record, source_cases),
        record_type=record_type,
        proposed_record=dict(proposed_record),
        source_cases=list(source_cases),
        teacher_reference=teacher_reference,
        teacher_approved=bool(teacher_approved),
        codex_approved=bool(codex_approved),
        evidence_policy={
            "teacher_reference_is_ground_truth": False,
            "facts_require_evidence": True,
            "judgments_are_reviewed_separately": True,
            "automatic_self_promotion_forbidden": True,
            "min_confirmed_cases": min_confirmed_cases,
            "required_approvals": ["external_teacher", "codex_developer"],
        },
        status=status,
        reason=reason,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return candidate.to_dict()


def can_promote_candidate(candidate: dict[str, Any]) -> bool:
    return str(candidate.get("status")) == "ready_for_human_merge"


def write_kb_candidate(candidate: dict[str, Any], *, root: Path, subdir: str = "artifacts/knowledge_candidates") -> Path:
    """Persist a staged candidate for human/teacher review."""

    candidate_id = str(candidate.get("candidate_id") or "")
    if not candidate_id:
        raise ValueError("candidate requires candidate_id")
    out_dir = root / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{candidate_id}.json"
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def update_kb_candidate_review(
    *,
    root: Path,
    candidate_id: str,
    teacher_approved: bool | None = None,
    codex_approved: bool | None = None,
    rejected_reason: str | None = None,
    subdir: str = "artifacts/knowledge_candidates",
    min_confirmed_cases: int = MIN_CONFIRMED_CASES,
) -> dict[str, Any]:
    """Apply human review marks to a staged candidate without promoting it."""

    path = root / subdir / f"{candidate_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"knowledge candidate not found: {candidate_id}")
    candidate = json.loads(path.read_text(encoding="utf-8"))
    if str(candidate.get("candidate_id")) != candidate_id:
        raise ValueError(f"candidate id mismatch in {path}")
    if rejected_reason:
        candidate["status"] = "rejected"
        candidate["reason"] = rejected_reason
        candidate["rejected_at"] = datetime.now(timezone.utc).isoformat()
    else:
        if teacher_approved is not None:
            candidate["teacher_approved"] = bool(teacher_approved)
        if codex_approved is not None:
            candidate["codex_approved"] = bool(codex_approved)
        status, reason = _admission_status(
            confirmed_cases=len(_confirmed_cases(list(candidate.get("source_cases") or []))),
            teacher_approved=bool(candidate.get("teacher_approved")),
            codex_approved=bool(candidate.get("codex_approved")),
            min_confirmed_cases=min_confirmed_cases,
        )
        candidate["status"] = status
        candidate["reason"] = reason
        candidate["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "artifact_type": "KnowledgeCandidateReviewUpdate",
        "status": "ok",
        "candidate_id": candidate_id,
        "candidate_status": candidate.get("status"),
        "reason": candidate.get("reason"),
        "path": path.as_posix(),
        "automatic_merge_performed": False,
    }


def build_manual_merge_block(*, root: Path, candidate_id: str, subdir: str = "artifacts/knowledge_candidates") -> dict[str, Any]:
    """Return an explicit controlled block for KB merge until a human edits KB records."""

    path = root / subdir / f"{candidate_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"knowledge candidate not found: {candidate_id}")
    candidate = json.loads(path.read_text(encoding="utf-8"))
    return {
        "artifact_type": "KnowledgeCandidateManualMerge",
        "status": "blocked",
        "candidate_id": candidate_id,
        "candidate_status": candidate.get("status"),
        "reason": "automatic KB merge is forbidden; human must merge the proposed record explicitly",
        "candidate_ready": can_promote_candidate(candidate),
        "automatic_merge_performed": False,
        "path": path.as_posix(),
    }


def load_kb_candidates(*, root: Path, subdir: str = "artifacts/knowledge_candidates") -> list[dict[str, Any]]:
    """Load persisted staged candidates."""

    directory = root / subdir
    if not directory.exists():
        return []
    rows = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("candidate_id"):
            rows.append(payload)
    return rows


def knowledge_candidate_report(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize review state without promoting anything."""

    by_status: dict[str, int] = {}
    by_record_type: dict[str, int] = {}
    for candidate in candidates:
        status = str(candidate.get("status") or "unknown")
        record_type = str(candidate.get("record_type") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_record_type[record_type] = by_record_type.get(record_type, 0) + 1
    return {
        "artifact_type": "KnowledgeCandidateReport",
        "candidate_count": len(candidates),
        "by_status": dict(sorted(by_status.items())),
        "by_record_type": dict(sorted(by_record_type.items())),
        "ready_for_human_merge": [candidate.get("candidate_id") for candidate in candidates if can_promote_candidate(candidate)],
        "policy": {
            "automatic_merge_forbidden": True,
            "human_review_required": True,
            "teacher_and_codex_approval_required": True,
        },
    }


def grouped_candidate_report(candidates: list[dict[str, Any]], *, min_confirmed_cases: int = MIN_CONFIRMED_CASES) -> dict[str, Any]:
    """Group staged candidates by proposed KB record identity."""

    groups: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        record = dict(candidate.get("proposed_record") or {})
        key = _candidate_group_key(candidate)
        group = groups.setdefault(
            key,
            {
                "group_key": key,
                "record_type": candidate.get("record_type"),
                "proposed_id": _proposed_id(record),
                "label": record.get("label"),
                "candidate_ids": [],
                "confirmed_cases": [],
                "teacher_approved": False,
                "codex_approved": False,
                "statuses": {},
            },
        )
        group["candidate_ids"].append(candidate.get("candidate_id"))
        group["teacher_approved"] = bool(group["teacher_approved"] or candidate.get("teacher_approved"))
        group["codex_approved"] = bool(group["codex_approved"] or candidate.get("codex_approved"))
        status = str(candidate.get("status") or "unknown")
        group["statuses"][status] = int(group["statuses"].get(status, 0)) + 1
        for case in candidate.get("source_cases", []):
            if isinstance(case, dict) and str(case.get("status")) in {"confirmed", "accepted", "verified"}:
                case_key = str(case.get("project") or case.get("url") or case)
                if case_key and not any(str(row.get("case_key")) == case_key for row in group["confirmed_cases"]):
                    group["confirmed_cases"].append({"case_key": case_key, **case})
    rows = []
    for group in groups.values():
        confirmed_count = len(group["confirmed_cases"])
        if confirmed_count < min_confirmed_cases:
            gate_status = "collect_more_cases"
            reason = f"needs {min_confirmed_cases} confirmed cases, has {confirmed_count}"
        elif not group["teacher_approved"]:
            gate_status = "needs_teacher_approval"
            reason = "external teacher/corrector has not approved the candidate group"
        elif not group["codex_approved"]:
            gate_status = "needs_codex_approval"
            reason = "Codex/developer approval is required before KB merge"
        else:
            gate_status = "ready_for_human_merge"
            reason = "confirmed by cases and both approval gates"
        rows.append({**group, "confirmed_case_count": confirmed_count, "gate_status": gate_status, "reason": reason})
    rows.sort(key=lambda row: (-int(row["confirmed_case_count"]), str(row["group_key"])))
    return {
        "artifact_type": "GroupedKnowledgeCandidateReport",
        "group_count": len(rows),
        "min_confirmed_cases": min_confirmed_cases,
        "groups": rows,
        "ready_for_human_merge": [row["group_key"] for row in rows if row["gate_status"] == "ready_for_human_merge"],
        "ready_for_teacher_review": [row["group_key"] for row in rows if row["gate_status"] == "needs_teacher_approval"],
        "policy": {
            "grouping_is_review_aid_only": True,
            "automatic_merge_forbidden": True,
            "teacher_and_codex_approval_required": True,
        },
    }


def kb_candidate_from_generic_project(
    *,
    project: str,
    proposed_rule_id: str,
    label: str,
    candidate_signals: list[str],
    first_slice_hint: str,
    source_cases: list[dict[str, Any]],
    teacher_reference: str,
    teacher_approved: bool = False,
    codex_approved: bool = False,
) -> dict[str, Any]:
    """Build a project-archetype candidate from repeated generic-analysis gaps."""

    proposed_record = {
        "record_type": "project_archetype_rule",
        "rule_id": proposed_rule_id,
        "archetype": proposed_rule_id,
        "label": label,
        "role_scope": ["project_analyzer", "architect", "spec_writer"],
        "evidence_strength": "weak",
        "match": {
            "text_contains_any": [project, *list(candidate_signals)],
            "required_contains_any": [project],
            "min_score": min(2, len(candidate_signals)) or 1,
        },
        "first_slice": {"name": first_slice_hint, "target_sources": ["central", "orchestrators", "broad"]},
        "candidate_origin": {"project": project, "reason": "generic project-analysis fallback"},
    }
    return build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record=proposed_record,
        source_cases=source_cases,
        teacher_reference=teacher_reference,
        teacher_approved=teacher_approved,
        codex_approved=codex_approved,
    )


def _candidate_group_key(candidate: dict[str, Any]) -> str:
    record = dict(candidate.get("proposed_record") or {})
    return f"{candidate.get('record_type')}:{_proposed_id(record)}"


def _proposed_id(record: dict[str, Any]) -> str:
    for key in ("rule_id", "pattern_id", "risk_id", "lesson_id", "fact_id"):
        value = record.get(key)
        if value:
            return str(value)
    return "unknown"


def _admission_status(
    *,
    confirmed_cases: int,
    teacher_approved: bool,
    codex_approved: bool,
    min_confirmed_cases: int,
) -> tuple[str, str]:
    if confirmed_cases < min_confirmed_cases:
        return "collect_more_cases", f"needs {min_confirmed_cases} confirmed cases, has {confirmed_cases}"
    if not teacher_approved:
        return "needs_teacher_approval", "external teacher/corrector has not approved the candidate"
    if not codex_approved:
        return "needs_codex_approval", "Codex/developer approval is required before KB merge"
    return "ready_for_human_merge", "confirmed by cases and both approval gates"


def _confirmed_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [case for case in cases if str(case.get("status")) in {"confirmed", "accepted", "verified"}]


def _candidate_id(record_type: str, proposed_record: dict[str, Any], source_cases: list[dict[str, Any]]) -> str:
    seed = f"{record_type}:{proposed_record}:{source_cases}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"kbc_{digest}"
