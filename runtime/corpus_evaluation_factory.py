"""Build contamination-aware evaluation splits from an existing project inventory."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "corpus_evaluation_factory.json"


class CorpusEvaluationFactoryError(ValueError):
    """Raised when an evaluation inventory or policy is unsafe."""


@lru_cache(maxsize=2)
def load_corpus_evaluation_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "corpus_evaluation_factory.v1":
        raise CorpusEvaluationFactoryError("corpus evaluation policy schema mismatch")
    if payload.get("status") != "active":
        raise CorpusEvaluationFactoryError("corpus evaluation policy must be active")
    if not payload.get("target_project_types"):
        raise CorpusEvaluationFactoryError("corpus evaluation targets are missing")
    invariants = dict(payload.get("invariants") or {})
    required = (
        "holdout_frozen_before_acquisition", "content_disjoint", "lineage_disjoint",
        "untouched_only", "network_fallback_only_on_shortage",
    )
    if not all(invariants.get(name) is True for name in required):
        raise CorpusEvaluationFactoryError("corpus evaluation invariants are incomplete")
    return payload


def build_corpus_evaluation_plan(
    records: list[dict[str, Any]], *, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    rules = policy or load_corpus_evaluation_policy()
    normalized = [_normalize(row) for row in records]
    eligible = [row for row in normalized if row["exposure"] == "untouched"]
    unique = _deduplicate(eligible)
    targets = [str(value) for value in rules["target_project_types"]]
    split_rows = []
    shortages = {}
    for project_type in targets:
        rows = [row for row in unique if row["project_type"] == project_type]
        split, shortage = _split_type(rows, project_type, rules)
        split_rows.append(split)
        shortages[project_type] = shortage
    unknown = _unknown_clusters(
        [row for row in unique if row["project_type"] == "unknown_new_archetype"],
        dict(rules["unknown_cluster_thresholds"]),
    )
    network_required = any(any(values.values()) for values in shortages.values())
    checks = {
        "all_inputs_untouched": all(row["exposure"] == "untouched" for row in unique),
        "all_content_unique": len(unique) == len({row["content_digest"] for row in unique}),
        "split_content_disjoint": all(row["checks"]["content_disjoint"] for row in split_rows),
        "split_lineage_disjoint": all(row["checks"]["lineage_disjoint"] for row in split_rows),
        "network_only_on_shortage": network_required == any(any(values.values()) for values in shortages.values()),
    }
    return {
        "artifact_type": "CorpusEvaluationPlan",
        "schema_version": "corpus_evaluation_plan.v1",
        "status": "local_corpus_sufficient" if not network_required else "local_corpus_shortage",
        "summary": {
            "inventory_records": len(records),
            "untouched_records": len(eligible),
            "unique_projects": len(unique),
            "duplicate_or_exposed_records": len(records) - len(unique),
        },
        "target_project_types": targets,
        "splits": split_rows,
        "shortages": shortages,
        "unknown_clusters": unknown,
        "network_fallback": {
            "allowed": network_required,
            "reason": "local_corpus_shortage" if network_required else "local_corpus_sufficient",
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "safety": {"source_apply": False, "automatic_promotion": False, "holdout_consumed": False},
    }


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    row = dict(raw)
    required = ("project", "project_type", "source_lineage", "content_digest")
    missing = [name for name in required if not str(row.get(name) or "")]
    if missing:
        raise CorpusEvaluationFactoryError(f"corpus record requires {missing[0]}")
    digest = str(row["content_digest"])
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise CorpusEvaluationFactoryError("corpus content digest is invalid")
    return {
        "project": str(row["project"]),
        "project_type": str(row["project_type"]),
        "source_lineage": str(row["source_lineage"]),
        "content_digest": digest,
        "exposure": str(row.get("exposure") or "unknown"),
        "markers": sorted({str(value) for value in row.get("markers") or [] if value}),
        "path": str(row.get("path") or ""),
    }


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_digest = {}
    for row in sorted(rows, key=lambda value: (value["content_digest"], value["project"])):
        by_digest.setdefault(row["content_digest"], row)
    return list(by_digest.values())


def _split_type(
    rows: list[dict[str, Any]], project_type: str, policy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    ordered = sorted(rows, key=lambda row: _split_key(row, str(policy["split_seed"])))
    holdout = _take_lineages(ordered, int(policy["minimum_holdout_per_type"]))
    blocked_lineages = {row["source_lineage"] for row in holdout}
    blocked_digests = {row["content_digest"] for row in holdout}
    acquisition = _take_lineages(
        [row for row in ordered if row["source_lineage"] not in blocked_lineages],
        int(policy["minimum_acquisition_per_type"]),
    )
    shortage = {
        "holdout": max(0, int(policy["minimum_holdout_per_type"]) - len(holdout)),
        "acquisition": max(0, int(policy["minimum_acquisition_per_type"]) - len(acquisition)),
    }
    return ({
        "project_type": project_type,
        "holdout": holdout,
        "acquisition": acquisition,
        "checks": {
            "content_disjoint": not blocked_digests.intersection(row["content_digest"] for row in acquisition),
            "lineage_disjoint": not blocked_lineages.intersection(row["source_lineage"] for row in acquisition),
        },
    }, shortage)


def _take_lineages(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected, lineages = [], set()
    for row in rows:
        if row["source_lineage"] in lineages:
            continue
        selected.append(row)
        lineages.add(row["source_lineage"])
        if len(selected) == count:
            break
    return selected


def _unknown_clusters(rows: list[dict[str, Any]], thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row["markers"])].append(row)
    result = []
    for markers, members in sorted(groups.items()):
        checks = {
            "minimum_projects": len({row["project"] for row in members}) >= int(thresholds["minimum_projects"]),
            "minimum_lineages": len({row["source_lineage"] for row in members}) >= int(thresholds["minimum_lineages"]),
            "minimum_content_digests": len({row["content_digest"] for row in members}) >= int(thresholds["minimum_content_digests"]),
            "minimum_markers": len(markers) >= int(thresholds["minimum_markers"]),
        }
        result.append({
            "cluster_id": "unknown_" + hashlib.sha256("|".join(markers).encode()).hexdigest()[:12],
            "markers": list(markers),
            "projects": sorted(row["project"] for row in members),
            "status": "research_candidate" if all(checks.values()) else "collect_more_cases",
            "checks": checks,
            "automatic_promotion": False,
        })
    return result


def _split_key(row: dict[str, Any], seed: str) -> str:
    return hashlib.sha256(
        f"{seed}:{row['project']}:{row['source_lineage']}:{row['content_digest']}".encode()
    ).hexdigest()
