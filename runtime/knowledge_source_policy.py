"""Source policy for external knowledge acquisition."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class KnowledgeSourcePolicy:
    source_type: str
    allowed_uses: list[str]
    forbidden_uses: list[str]
    required_checks: list[str]
    confidence_cap: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def github_source_policy() -> KnowledgeSourcePolicy:
    return KnowledgeSourcePolicy(
        source_type="github_repository_search",
        allowed_uses=[
            "implementation pattern discovery",
            "library candidate discovery",
            "edge-case discovery",
            "test scenario inspiration",
        ],
        forbidden_uses=[
            "copy code verbatim",
            "treat popularity as correctness",
            "override official documentation",
            "change architecture without local evidence",
        ],
        required_checks=["license awareness", "official docs follow-up", "local contract tests", "security review"],
        confidence_cap=0.65,
    )


def official_docs_source_policy() -> KnowledgeSourcePolicy:
    return KnowledgeSourcePolicy(
        source_type="official_docs_fetch",
        allowed_uses=[
            "API contract verification",
            "library behavior verification",
            "installation or backend availability guidance",
            "version-sensitive implementation notes",
        ],
        forbidden_uses=[
            "execute documentation examples without local tests",
            "treat documentation excerpt as project-specific evidence",
            "bypass local capability contracts",
            "change registry lifecycle without runtime evidence",
        ],
        required_checks=["allowlisted domain", "fresh local fetch", "local contract tests", "source citation in artifact"],
        confidence_cap=0.85,
    )
