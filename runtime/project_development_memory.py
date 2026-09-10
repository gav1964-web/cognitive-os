"""Memory context helpers for project development."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _memory_context(project_dir: Path, prior_runs: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = project_dir.resolve().as_posix().lower()
    relevant = [row for row in prior_runs if str(row.get("project_root") or "").lower() == resolved]
    claimed = [
        row
        for row in relevant
        if dict(row.get("validated_memory") or {}).get("status") == "validated"
    ]
    validated = [
        dict(row.get("validated_memory") or {})
        for row in claimed
        if dict(dict(row.get("recognition") or {}).get("pilot_route") or {}).get("status")
        == "eligible_for_full_chain"
    ]
    return {
        "artifact_type": "ProjectDevelopmentMemoryContext",
        "prior_run_count": len(relevant),
        "prior_decisions": [dict(row.get("decision") or {}).get("selected_option") for row in relevant[-5:]],
        "prior_outcomes": [dict(row.get("outcome_contract") or {}).get("status") for row in relevant[-5:]],
        "validated_memory_count": len(validated),
        "validated_memories": validated[-5:],
        "rejected_validated_memory_count": len(claimed) - len(validated),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
