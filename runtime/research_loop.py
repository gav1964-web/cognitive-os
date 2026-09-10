"""Bounded external-research loop for unresolved knowledge gaps."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .knowledge import github_repository_knowledge, official_docs_knowledge


@dataclass(frozen=True)
class KnowledgeGapPacket:
    gap_id: str
    question: str
    needed_for: str
    role: str
    reason: str
    acceptable_sources: list[str]
    confidence_required: float
    decision_if_unresolved: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchPlanStep:
    step_id: str
    source_type: str
    query: str
    purpose: str
    execute_by_default: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_knowledge_gap_packet(
    *,
    question: str,
    needed_for: str,
    role: str,
    reason: str,
    acceptable_sources: list[str] | None = None,
    confidence_required: float = 0.7,
    decision_if_unresolved: str = "Ask clarification or continue with local evidence only.",
) -> dict[str, Any]:
    sources = acceptable_sources or ["official_docs_fetch", "github_repository_search", "user_clarification"]
    packet = KnowledgeGapPacket(
        gap_id=_id("kgp", f"{question}:{needed_for}:{role}:{reason}"),
        question=question,
        needed_for=needed_for,
        role=role,
        reason=reason,
        acceptable_sources=sources,
        confidence_required=float(confidence_required),
        decision_if_unresolved=decision_if_unresolved,
    )
    return packet.to_dict()


def build_research_plan(gap: dict[str, Any], *, query_hint: str | None = None) -> dict[str, Any]:
    """Create a bounded plan; steps are not automatically executed by role code."""

    sources = [str(item) for item in gap.get("acceptable_sources", [])]
    query = query_hint or str(gap.get("question") or "")
    steps: list[ResearchPlanStep] = []
    if "official_docs_fetch" in sources:
        steps.append(
            ResearchPlanStep(
                step_id="research_official_docs",
                source_type="official_docs_fetch",
                query=query,
                purpose="verify API/domain facts against official documentation",
                execute_by_default=False,
            )
        )
    if "github_repository_search" in sources:
        steps.append(
            ResearchPlanStep(
                step_id="research_github_examples",
                source_type="github_repository_search",
                query=query,
                purpose="find comparable projects and edge-case patterns; never copy code",
                execute_by_default=False,
            )
        )
    if "user_clarification" in sources:
        steps.append(
            ResearchPlanStep(
                step_id="ask_user_clarification",
                source_type="user_clarification",
                query=str(gap.get("question") or ""),
                purpose="ask the human for missing requirements or domain facts",
                execute_by_default=True,
            )
        )
    return {
        "artifact_type": "ResearchPlan",
        "gap_id": gap.get("gap_id"),
        "steps": [step.to_dict() for step in steps],
        "policy": {
            "llm_may_not_browse_freely": True,
            "external_sources_are_evidence": True,
            "source_digest_required": True,
            "kb_promotion_requires_admission_gate": True,
        },
    }


def execute_research_plan(
    gap: dict[str, Any],
    plan: dict[str, Any],
    *,
    official_docs_urls: list[str] | None = None,
    github_limit: int = 5,
) -> dict[str, Any]:
    """Execute only concrete allowlisted research steps provided by the caller."""

    digests = []
    docs_urls = list(official_docs_urls or [])
    for step in plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        source_type = str(step.get("source_type") or "")
        if source_type == "official_docs_fetch":
            for url in docs_urls:
                result = official_docs_knowledge(url, question=str(gap.get("question") or ""), needed_for=str(gap.get("needed_for") or ""))
                digests.append(source_digest_from_knowledge_result(result, source_type=source_type))
        elif source_type == "github_repository_search":
            result = github_repository_knowledge(str(step.get("query") or gap.get("question") or ""), needed_for=str(gap.get("needed_for") or ""), limit=github_limit)
            digests.append(source_digest_from_knowledge_result(result, source_type=source_type))
    status = "ok" if digests else "not_executed"
    return {
        "artifact_type": "ResearchResult",
        "gap_id": gap.get("gap_id"),
        "status": status,
        "source_digests": digests,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "research result is evidence, not ground truth",
            "KB promotion requires repeated confirmed cases plus teacher and Codex approval",
        ],
    }


def source_digest_from_knowledge_result(result: dict[str, Any], *, source_type: str) -> dict[str, Any]:
    artifacts = [row for row in result.get("knowledge_artifacts", []) if isinstance(row, dict)]
    facts = [str(row.get("extracted_fact") or "") for row in artifacts]
    confidence = max([float(row.get("confidence") or 0) for row in artifacts] or [0.0])
    return {
        "artifact_type": "SourceDigest",
        "source_type": source_type,
        "status": result.get("status"),
        "facts": facts,
        "confidence": confidence,
        "evidence_hash": _id("sd", f"{source_type}:{facts}:{confidence}"),
        "limitations": [item for row in artifacts for item in row.get("limitations", [])][:6],
    }


def project_research_gap_from_synthesis(synthesis: dict[str, Any]) -> dict[str, Any] | None:
    """Ask for research when architecture synthesis only found generic/weak knowledge."""

    profile = dict(synthesis.get("project_profile") or {})
    rule = str(profile.get("knowledge_rule") or synthesis.get("knowledge", {}).get("matched_rule") or "")
    confidence = str(synthesis.get("confidence") or "")
    if rule != "python_project" and confidence != "low":
        return None
    root = str(profile.get("root") or "project")
    question = f"What project archetype and first-slice strategy fit {root}?"
    return build_knowledge_gap_packet(
        question=question,
        needed_for="project architecture synthesis",
        role="architect",
        reason=f"matched_rule={rule or 'unknown'}, confidence={confidence or 'unknown'}",
        acceptable_sources=["github_repository_search", "user_clarification"],
        confidence_required=0.7,
        decision_if_unresolved="Keep generic Python-project advice and request teacher review.",
    )


def _id(prefix: str, seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}_{digest}"
