"""Qualify mined historical defects while keeping the upstream fix sealed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .historical_defect_sandbox import qualify_candidate_in_sandbox
from .historical_defect_environment import validate_environment_profile
from .local_historical_defect_evidence import evidence_digest, inside, write_manifests
from .local_historical_defect_mining import TARGET_TYPES


class HistoricalDefectQualificationError(ValueError):
    """Raised when public and sealed qualification inputs do not bind."""


def qualify_historical_defects(
    *, root: Path, public: dict[str, Any], oracle: dict[str, Any],
    timeout: int = 180, write: bool = False,
    environments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = root.resolve()
    _validate_manifests(public, oracle, root=base, timeout=timeout)
    profiles = _environment_profiles(base, public, environments) if environments is not None else {}
    oracle_by_id = {str(row["candidate_id"]): dict(row) for row in oracle["cases"]}
    public_results, sealed_results = [], []
    for case in public["cases"]:
        candidate_id = str(case["candidate_id"])
        sealed = oracle_by_id[candidate_id]
        outcome = qualify_candidate_in_sandbox(
            root=base, public=dict(case), oracle=sealed, timeout=timeout,
            environment_profile=profiles.get(candidate_id),
        )
        public_results.append(_public_result(dict(case), outcome))
        sealed_results.append({
            "candidate_id": candidate_id,
            "fix_revision": sealed.get("fix_revision"),
            "production_files": sealed.get("production_files"),
            "production_patch_sha256": sealed.get("production_patch_sha256"),
            "outcome": outcome,
        })
    qualified_counts = {
        name: sum(
            row["project_stratum"] == name and row["status"] == "qualified"
            for row in public_results
        )
        for name in TARGET_TYPES
    }
    ready = all(qualified_counts[name] >= 2 for name in TARGET_TYPES)
    checks = {
        "public_manifest_bound": oracle.get("public_manifest_digest") == public.get("manifest_digest"),
        "candidate_sets_match": set(oracle_by_id) == {
            str(row["candidate_id"]) for row in public["cases"]
        },
        "two_qualified_per_type": ready,
        "source_heads_unchanged": all(row["source_head_unchanged"] for row in public_results),
        "source_worktrees_unchanged": all(row["source_worktree_unchanged"] for row in public_results),
        "source_worktree_registries_unchanged": all(
            row["source_worktree_registry_unchanged"] for row in public_results
        ),
        "sandboxes_cleaned": all(row["sandbox_cleaned"] for row in public_results),
        "qualification_environments_ready": all(
            dict(row.get("environment_bootstrap") or {}).get("kind") == "isolated_venv"
            for row in public_results
        ),
        "fix_oracle_not_disclosed": all(
            "fix_revision" not in row and "production_files" not in row
            for row in public_results
        ),
        "no_source_apply": True,
        "no_automatic_promotion": True,
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    public_receipt = {
        "artifact_type": "HistoricalDefectQualificationReceipt",
        "schema_version": "historical_defect_qualification_receipt.v2",
        "status": "ready_for_role_evaluation" if all(checks.values()) else "insufficient_qualified_defects",
        "generated_at": generated_at,
        "source_public_manifest_digest": public.get("manifest_digest"),
        "source_environment_bundle_digest": (environments or {}).get("bundle_digest"),
        "summary": {
            "evaluated": len(public_results), "qualified_counts": qualified_counts,
            "environment_blocked": sum(row["status"] == "environment_blocked" for row in public_results),
            "not_reproduced": sum(row["status"] == "not_reproduced" for row in public_results),
        },
        "cases": public_results,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "role_holdout_consumed": False,
        "oracle_disclosure": "separate_file_not_for_role_input",
        "safety": {"source_apply": False, "automatic_promotion": False},
    }
    public_receipt["receipt_digest"] = evidence_digest(public_receipt)
    sealed_receipt = {
        "artifact_type": "HistoricalDefectQualificationOracleReceipt",
        "schema_version": "historical_defect_qualification_oracle_receipt.v2",
        "status": "sealed", "generated_at": generated_at,
        "public_receipt_digest": public_receipt["receipt_digest"],
        "cases": sealed_results,
        "disclosure_policy": "withhold_until_role_outcome_is_frozen",
    }
    sealed_receipt["oracle_receipt_digest"] = evidence_digest(sealed_receipt)
    paths = _write(base, public_receipt, sealed_receipt) if write else {}
    return {"public_receipt": public_receipt, "oracle_receipt": sealed_receipt, "paths": paths}


def _validate_manifests(
    public: dict[str, Any], oracle: dict[str, Any], *, root: Path, timeout: int,
) -> None:
    if public.get("schema_version") != "local_historical_defect_public_manifest.v1":
        raise HistoricalDefectQualificationError("public defect manifest schema mismatch")
    if public.get("status") not in {"ready", "shortage"}:
        raise HistoricalDefectQualificationError("public defect manifest status is invalid")
    selection_checks = {
        name: passed for name, passed in dict(public.get("checks") or {}).items()
        if name != "minimum_candidates_met"
    }
    if not selection_checks or not all(selection_checks.values()):
        raise HistoricalDefectQualificationError("public defect selection checks failed")
    if oracle.get("schema_version") != "local_historical_defect_oracle.v1" or oracle.get("status") != "sealed":
        raise HistoricalDefectQualificationError("defect oracle is not sealed")
    public_body = {key: value for key, value in public.items() if key != "manifest_digest"}
    if evidence_digest(public_body) != public.get("manifest_digest"):
        raise HistoricalDefectQualificationError("public defect manifest digest mismatch")
    if oracle.get("public_manifest_digest") != public.get("manifest_digest"):
        raise HistoricalDefectQualificationError("defect oracle does not bind public manifest")
    oracle_body = {key: value for key, value in oracle.items() if key != "oracle_digest"}
    if evidence_digest(oracle_body) != oracle.get("oracle_digest"):
        raise HistoricalDefectQualificationError("defect oracle digest mismatch")
    public_cases = public.get("cases") or []
    oracle_cases = oracle.get("cases") or []
    public_ids = {str(row.get("candidate_id") or "") for row in public.get("cases") or []}
    oracle_ids = {str(row.get("candidate_id") or "") for row in oracle.get("cases") or []}
    if not 1 <= len(public_ids) <= 4 or public_ids != oracle_ids or "" in public_ids:
        raise HistoricalDefectQualificationError("defect candidate sets do not match")
    if len(public_ids) != len(public_cases) or len(oracle_ids) != len(oracle_cases):
        raise HistoricalDefectQualificationError("defect candidates must be unique")
    if any(row.get("project_stratum") not in TARGET_TYPES for row in public["cases"]):
        raise HistoricalDefectQualificationError("defect candidate stratum is invalid")
    if not all(row.get("project_root") for row in public_cases):
        raise HistoricalDefectQualificationError("defect project roots are required")
    projects = [inside(root, str(row["project_root"])) for row in public_cases]
    if len(projects) != len(set(projects)):
        raise HistoricalDefectQualificationError("defect projects must be independent")
    for project_type in TARGET_TYPES:
        owners = [
            str(row.get("owner") or "") for row in public_cases
            if row["project_stratum"] == project_type
        ]
        if not all(owners) or len(owners) != len(set(owners)):
            raise HistoricalDefectQualificationError("defect owners must be independent per type")
    if not 10 <= timeout <= 600:
        raise HistoricalDefectQualificationError("qualification timeout is outside bounded limits")


def _public_result(case: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": case.get("candidate_id"),
        "project": case.get("project"),
        "project_stratum": case.get("project_stratum"),
        "owner": case.get("owner"),
        "project_root": case.get("project_root"),
        "baseline_revision": case.get("baseline_revision"),
        "candidate_test_files": case.get("candidate_test_files"),
        "candidate_test_support_files": case.get("candidate_test_support_files"),
        "status": outcome.get("status"), "reason": outcome.get("reason"),
        "baseline": outcome.get("baseline"),
        "baseline_repeats": outcome.get("baseline_repeats"),
        "comparison_checks": outcome.get("comparison_checks"),
        "environment_bootstrap": outcome.get("environment_bootstrap"),
        "upstream_fix_confirmed": outcome.get("status") == "qualified",
        "source_head_unchanged": outcome.get("source_head_unchanged") is True,
        "source_worktree_unchanged": outcome.get("source_worktree_unchanged") is True,
        "source_worktree_registry_unchanged": outcome.get("source_worktree_registry_unchanged") is True,
        "sandbox_cleaned": outcome.get("sandbox_cleaned") is True,
    }


def _write(
    root: Path, public: dict[str, Any], oracle: dict[str, Any],
) -> dict[str, str]:
    paths = write_manifests(root, public, oracle)
    return {"public": paths["public"], "oracle": paths["oracle"]}


def read_qualification_inputs(
    root: Path, public_path: str, oracle_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(inside(root, public_path).read_text(encoding="utf-8")),
        json.loads(inside(root, oracle_path).read_text(encoding="utf-8")),
    )


def _environment_profiles(
    root: Path, public: dict[str, Any], bundle: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if bundle.get("schema_version") != "historical_defect_environment_bundle.v1":
        raise HistoricalDefectQualificationError("qualification environment bundle schema mismatch")
    body = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    if evidence_digest(body) != bundle.get("bundle_digest"):
        raise HistoricalDefectQualificationError("qualification environment bundle digest mismatch")
    if bundle.get("public_manifest_digest") != public.get("manifest_digest"):
        raise HistoricalDefectQualificationError("qualification environments do not bind public manifest")
    profiles = dict(bundle.get("profiles") or {})
    if set(profiles) - {row["candidate_id"] for row in public["cases"]}:
        raise HistoricalDefectQualificationError("qualification environment candidate set mismatch")
    for profile in profiles.values():
        validate_environment_profile(root, profile)
    return profiles
