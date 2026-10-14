"""Admission gates for the first bounded Cognitive OS pilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "config" / "pilot_profile.json"


def load_pilot_profile(path: Path | None = None) -> dict[str, Any]:
    profile = json.loads((path or DEFAULT_PROFILE).read_text(encoding="utf-8"))
    required = {"profile_id", "allowed_project_strata", "allowed_modes", "prohibited_risk_profiles", "transfer_gate"}
    if not required <= set(profile):
        raise ValueError(f"pilot profile is missing fields: {sorted(required - set(profile))}")
    return profile


def evaluate_pilot_candidate(
    *,
    project_stratum: str,
    risk_profiles: list[str],
    effect_mode: str,
    requested_mode: str,
    role_readiness: dict[str, Any],
    transfer_evidence: dict[str, Any],
    reviewer_adversarial: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = profile or load_pilot_profile()
    roles = dict(role_readiness.get("roles") or {})
    transfer = dict(policy.get("transfer_gate") or {})
    prohibited = set(policy.get("prohibited_risk_profiles") or [])
    checks = {
        "project_stratum_allowed": project_stratum in set(policy.get("allowed_project_strata") or []),
        "risk_profile_allowed": not (set(risk_profiles) & prohibited),
        "effect_mode_allowed": effect_mode in set(policy.get("allowed_effect_modes") or []),
        "requested_mode_allowed": requested_mode in set(policy.get("allowed_modes") or []),
        "required_roles_ready": all(dict(roles.get(role) or {}).get("mvp_ready") is True for role in policy.get("required_roles") or []),
        "blind_project_floor_met": int(transfer_evidence.get("blind_projects") or 0) >= int(transfer.get("minimum_blind_projects") or 0),
        "independent_lineage_floor_met": int(transfer_evidence.get("independent_lineages") or 0) >= int(transfer.get("minimum_independent_lineages") or 0),
        "handoff_loss_within_limit": int(transfer_evidence.get("handoff_loss") or 0) <= int(transfer.get("maximum_handoff_loss") or 0),
        "reviewer_adversarial_green": reviewer_adversarial.get("status") == "ok",
        "source_apply_disabled": dict(policy.get("source_apply") or {}).get("allowed") is False,
    }
    return {
        "artifact_type": "PilotAdmissionDecision",
        "profile_id": policy.get("profile_id"),
        "status": "eligible" if all(checks.values()) else "blocked",
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "execution_policy": {
            "requested_mode": requested_mode,
            "source_apply_allowed": False,
            "human_supervision_required": True,
        },
    }
