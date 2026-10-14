"""Iteration assessment and rollback for autonomous role improvement."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from .project_evolution_policy import load_project_evolution_policy


def capture_promotion_state(root: Path) -> dict[str, bytes | None]:
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    paths = [str(item) for item in policy.get("promotion_transaction_paths", []) if item]
    return {
        path: (root / path).read_bytes() if (root / path).is_file() else None
        for path in paths
    }


def changed_promotion_paths(root: Path, snapshot: dict[str, bytes | None]) -> list[str]:
    return [
        path for path, before in snapshot.items()
        if ((root / path).read_bytes() if (root / path).is_file() else None) != before
    ]


def rollback_promotion_state(root: Path, snapshot: dict[str, bytes | None]) -> list[str]:
    changed = changed_promotion_paths(root, snapshot)
    for relative in changed:
        path = root / relative
        before = snapshot[relative]
        if before is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write(path, before)
    _clear_caches()
    return changed


def assess_iteration(
    before: dict[str, Any], after: dict[str, Any], *, target_score: float
) -> dict[str, Any]:
    prior = _scored_cases(before)
    current = _scored_cases(after)
    shared = sorted(set(prior) & set(current))
    regressions = [
        name for name in shared
        if current[name]["score"] < prior[name]["score"]
        or _status_rank(current[name]["status"]) < _status_rank(prior[name]["status"])
    ]
    prior_failures = sum(row["status"] != "ok" or row["score"] < target_score for row in prior.values())
    current_failures = sum(row["status"] != "ok" or row["score"] < target_score for row in current.values())
    prior_total = round(sum(row["score"] for row in prior.values()), 4)
    current_total = round(sum(row["score"] for row in current.values()), 4)
    improved = current_failures < prior_failures or current_total > prior_total
    return {
        "status": "accepted" if improved and not regressions else "rejected",
        "improved": improved,
        "regressions": regressions,
        "failure_count_before": prior_failures,
        "failure_count_after": current_failures,
        "score_total_before": prior_total,
        "score_total_after": current_total,
    }


def snapshot_digest(snapshot: dict[str, bytes | None]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(snapshot.items()):
        digest.update(path.encode("utf-8")); digest.update(content or b"")
    return digest.hexdigest()


def _scored_cases(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("project")): {
            "score": float(row.get("project_min_score") or 0.0),
            "status": str(row.get("status") or "needs_review"),
        }
        for row in list(report.get("cases") or [])
        if row.get("status") != "out_of_scope"
    }


def _status_rank(status: str) -> int:
    return {"needs_review": 0, "blocked_ok": 1, "ok": 2}.get(status, 0)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content); temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _clear_caches() -> None:
    from .executable_acceptance_policy import clear_executable_acceptance_policy_cache
    from .promoted_candidate_selection_policies import load_selection_policies
    from .promoted_executable_adapters import load_executable_adapters
    from .promoted_semantic_contract_profiles import load_promoted_profiles

    clear_executable_acceptance_policy_cache()
    load_selection_policies.cache_clear()
    load_executable_adapters.cache_clear()
    load_promoted_profiles.cache_clear()
