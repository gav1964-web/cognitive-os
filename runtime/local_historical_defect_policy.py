"""Validated policy and scope for local historical defect selection."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "local_historical_defect_mining.json"
SCHEMA_VERSION = "local_historical_defect_mining.v1"
TARGET_TYPES = ("cli_local_tool", "library_pure_transform")


from cognitive_replay.git import HistoricalDefectMiningError


@lru_cache(maxsize=1)
def load_historical_mining_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("status") != "active":
        raise HistoricalDefectMiningError("historical mining policy is not active")
    if tuple(payload.get("target_project_types") or ()) != TARGET_TYPES:
        raise HistoricalDefectMiningError("historical mining target types are invalid")
    positive = (
        "minimum_candidates_per_type", "scan_limit", "max_commits_per_project",
        "max_changed_files", "max_production_python_files", "max_test_python_files",
    )
    if any(int(payload.get(name) or 0) < 1 for name in positive):
        raise HistoricalDefectMiningError("historical mining limits must be positive")
    if not all(payload.get(name) for name in (
        "prospective_evidence_glob", "native_failure_evidence_glob",
        "historical_selection_evidence_glob",
    )):
        raise HistoricalDefectMiningError("historical mining exposure evidence is incomplete")
    invariants = dict(payload.get("invariants") or {})
    required_true = (
        "local_corpus_first", "untouched_projects_only", "owner_independent",
        "production_and_test_delta_required", "baseline_frozen_before_execution",
        "fix_oracle_separated",
    )
    if not all(invariants.get(name) is True for name in required_true):
        raise HistoricalDefectMiningError("historical mining invariants are incomplete")
    if invariants.get("source_apply") is not False or invariants.get("automatic_promotion") is not False:
        raise HistoricalDefectMiningError("historical mining mutation boundary is unsafe")
    return payload
