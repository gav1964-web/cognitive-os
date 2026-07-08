"""Knowledge gap artifacts and local acquisition helpers."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from plugins.inspect_installed_packages.src.main import run as inspect_installed_packages
from plugins.github_repository_search.src.main import run as github_repository_search
from plugins.official_docs_fetch.src.main import run as official_docs_fetch
from .goal_orchestrator import GoalDecision
from .knowledge_source_policy import github_source_policy, official_docs_source_policy


@dataclass(frozen=True)
class KnowledgeGap:
    gap_id: str
    question: str
    needed_for: str
    acceptable_sources: list[str]
    confidence_required: float
    decision_if_unresolved: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeArtifact:
    gap_id: str
    source: str
    evidence: dict[str, Any]
    extracted_fact: str
    confidence: float
    collected_at: str
    expires_at: str | None
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def knowledge_preflight(goal: str, root_input: dict[str, Any]) -> dict[str, Any]:
    gap = _xls_backend_gap(goal, root_input)
    if gap is None:
        return {"status": "skipped", "knowledge_gaps": [], "knowledge_artifacts": [], "route_override": None}
    artifact = _inspect_xls_backends(gap)
    unresolved = artifact.confidence < gap.confidence_required
    return {
        "status": "blocked" if unresolved else "ok",
        "knowledge_gaps": [gap.to_dict()],
        "knowledge_artifacts": [artifact.to_dict()],
        "route_override": {
            "action": "STOP_UNSUPPORTED",
            "reason_code": "L4_KNOWLEDGE_GAP_UNRESOLVED",
            "message": gap.decision_if_unresolved,
        }
        if unresolved
        else None,
    }


def apply_knowledge_route_override(goal: str, decision: GoalDecision, knowledge: dict[str, Any]) -> GoalDecision:
    override = dict(knowledge.get("route_override") or {})
    if not override:
        return decision
    return GoalDecision(
        action=str(override["action"]),
        reason_code=str(override["reason_code"]),
        goal=goal,
        normalized_goal=" ".join(goal.strip().lower().split()),
        required_capabilities=[],
    )


def github_repository_knowledge(query: str, *, needed_for: str, limit: int = 5) -> dict[str, Any]:
    policy = github_source_policy()
    gap = KnowledgeGap(
        gap_id=_gap_id("github_repository_search", query),
        question=f"What public GitHub repositories may provide evidence for: {query}?",
        needed_for=needed_for,
        acceptable_sources=[policy.source_type],
        confidence_required=0.5,
        decision_if_unresolved="Continue without GitHub evidence or ask for another source.",
    )
    evidence = github_repository_search({"query": query, "limit": limit})
    repos = list(evidence.get("repositories", []))
    artifact = KnowledgeArtifact(
        gap_id=gap.gap_id,
        source=policy.source_type,
        evidence={"policy": policy.to_dict(), **evidence},
        extracted_fact=_github_fact(repos),
        confidence=min(policy.confidence_cap, 0.25 + 0.08 * len(repos)),
        collected_at=datetime.now(timezone.utc).isoformat(),
        expires_at=None,
        limitations=[
            "GitHub repository search is external evidence, not ground truth",
            "repository popularity does not imply correctness",
            "code must not be copied without license review",
            "official docs and local contract tests are still required",
        ],
    )
    return {"status": "ok" if repos else "no_results", "knowledge_gaps": [gap.to_dict()], "knowledge_artifacts": [artifact.to_dict()]}


def official_docs_knowledge(url: str, *, question: str, needed_for: str, max_chars: int = 4000) -> dict[str, Any]:
    policy = official_docs_source_policy()
    gap = KnowledgeGap(
        gap_id=_gap_id("official_docs_fetch", f"{url}:{question}"),
        question=question,
        needed_for=needed_for,
        acceptable_sources=[policy.source_type],
        confidence_required=0.75,
        decision_if_unresolved="Ask for an allowlisted official documentation URL or continue with local evidence only.",
    )
    evidence = official_docs_fetch({"url": url, "max_chars": max_chars})
    artifact = KnowledgeArtifact(
        gap_id=gap.gap_id,
        source=policy.source_type,
        evidence={"policy": policy.to_dict(), **evidence},
        extracted_fact=_official_docs_fact(evidence),
        confidence=policy.confidence_cap,
        collected_at=datetime.now(timezone.utc).isoformat(),
        expires_at=None,
        limitations=[
            "official documentation excerpt is external evidence, not project-specific proof",
            "local contract tests and runtime validation are still required",
            "only allowlisted documentation domains may be fetched",
        ],
    )
    return {"status": "ok", "knowledge_gaps": [gap.to_dict()], "knowledge_artifacts": [artifact.to_dict()]}


def _xls_backend_gap(goal: str, root_input: dict[str, Any]) -> KnowledgeGap | None:
    text = " ".join([goal, str(root_input.get("input_path", "")), str(root_input.get("output_path", ""))]).lower()
    if ".xls" not in text and " xls " not in f" {text} ":
        return None
    return KnowledgeGap(
        gap_id=_gap_id("legacy_xls_backend", text),
        question="Is a legacy .xls backend available in the current Python environment?",
        needed_for="decide whether spreadsheet conversion can safely handle legacy .xls",
        acceptable_sources=["installed_package_probe"],
        confidence_required=0.8,
        decision_if_unresolved="Stop before execution and request an optional xlrd/xlwt backend for legacy .xls.",
    )


def _inspect_xls_backends(gap: KnowledgeGap) -> KnowledgeArtifact:
    evidence = inspect_installed_packages({"packages": ["xlrd", "xlwt"]})
    available = [row["package"] for row in evidence["packages"] if row.get("available")]
    fact = "legacy .xls backend available" if available else "legacy .xls backend is not available"
    return KnowledgeArtifact(
        gap_id=gap.gap_id,
        source="inspect_installed_packages",
        evidence=evidence,
        extracted_fact=fact,
        confidence=0.95 if available else 0.7,
        collected_at=datetime.now(timezone.utc).isoformat(),
        expires_at=None,
        limitations=["importability probe only; does not validate real .xls read/write behavior"],
    )


def _gap_id(kind: str, seed: str) -> str:
    digest = hashlib.sha256(f"{kind}:{seed}".encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"kg_{digest}"


def _github_fact(repos: list[dict[str, Any]]) -> str:
    if not repos:
        return "GitHub repository search returned no candidates"
    names = ", ".join(str(repo.get("full_name")) for repo in repos[:3])
    return f"GitHub repository search returned {len(repos)} candidate repositories: {names}"


def _official_docs_fact(evidence: dict[str, object]) -> str:
    title = str(evidence.get("title") or "official documentation")
    domain = str(evidence.get("domain") or "unknown domain")
    chars = int(evidence.get("fetched_chars") or 0)
    return f"Official documentation fetched from {domain}: {title} ({chars} chars excerpt)"
