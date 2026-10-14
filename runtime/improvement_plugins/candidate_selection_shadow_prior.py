"""Use confirmed contrast patterns to order bounded shadow candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.improvement_plugins.candidate_selection_contrast_store import contrast_groups
from runtime.improvement_plugins.candidate_selection_holdout import partition_holdout_project
from runtime.improvement_plugins.candidate_selection_synthesis import (
    synthesized_discriminator_families,
)
from runtime.promoted_candidate_selection_policies import contrast_matches_policy
from runtime.source_target_evidence import source_target_evidence


def prioritize_shadow_candidates(
    *, root: Path, project_dir: Path, candidates: list[str],
    packet: dict[str, Any], failure_class: str, minimum_support: int = 2,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Order candidates by portable KB priors while keeping trials authoritative."""
    training, _holdout = partition_holdout_project(
        contrast_groups(root), project_dir.name, failure_class,
    )
    families = [
        row for row in synthesized_discriminator_families(training)
        if len(row.get("projects") or []) >= max(2, minimum_support)
    ]
    failed = _failed_evidence(packet)
    signal = str(
        dict(packet.get("downstream_evidence") or {}).get("acceptance_signal")
        or "meta_only"
    )
    scored = []
    for index, candidate in enumerate(candidates):
        evidence = _target_evidence(project_dir, candidate)
        matched = [
            row for row in families
            if signal in {str(value) for value in row["policy"].get("trigger_signals") or []}
            and contrast_matches_policy(failed, evidence, row["policy"])
        ]
        support = sum(len(row.get("projects") or []) for row in matched)
        readiness = _fixture_readiness(evidence) if support else (0, 0, 0, 0)
        scored.append((candidate, support, len(matched), readiness, index, matched))
    ordered = sorted(scored, key=lambda row: (-row[1], -row[2], row[3], row[4]))
    trace = [
        {
            "candidate": candidate,
            "support": support,
            "matched_policy_ids": [str(row["id"]) for row in matched],
        }
        for candidate, support, _count, _readiness, _index, matched in ordered if support
    ]
    return [row[0] for row in ordered], trace


def _failed_evidence(packet: dict[str, Any]) -> dict[str, Any]:
    quality = dict(packet.get("candidate_quality") or {})
    structural = dict(quality.get("structural_evidence") or {})
    selection = dict(quality.get("selection_evidence") or {})
    return {
        **structural,
        "ranking_reasons": list(selection.get("ranking_reasons") or []),
        "dependency_readiness": dict(selection.get("dependency_readiness") or {}),
    }


def _target_evidence(project_dir: Path, target: str) -> dict[str, Any]:
    source = source_target_evidence(project_dir, target)
    snippet = dict(source.get("snippet") or {})
    structural = dict(snippet.get("structural_contract") or {})
    return {**structural, "ranking_reasons": []}


def _fixture_readiness(evidence: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(not evidence.get("source_body_complete")),
        int(evidence.get("argument_count") or 0),
        len(evidence.get("called_operations") or []),
        -int(evidence.get("return_paths") or 0),
    )
