"""Promotion gates for honest role score growth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "role_promotion_policy.json"


class RolePromotionPolicyError(RuntimeError):
    """Raised when role promotion policy is invalid."""


def load_role_promotion_policy(path: str | Path | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "role_promotion_policy.v1":
        raise RolePromotionPolicyError("role promotion policy must use schema_version role_promotion_policy.v1")
    if payload.get("status") != "active":
        raise RolePromotionPolicyError("role promotion policy must be active")
    _validate(payload)
    return payload


def _validate(payload: dict[str, Any]) -> None:
    bands = dict(payload.get("score_bands") or {})
    roles = dict(payload.get("first_four_roles") or {})
    boundary = dict(dict(payload.get("scope_boundary") or {}).get("foundation_roles_1_3") or {})
    if boundary.get("applies_to") != "Python-owned boundary":
        raise RolePromotionPolicyError("foundation roles 1-3 must declare Python-owned boundary")
    if not boundary.get("excluded") or "out_of_scope" not in str(boundary.get("rule") or ""):
        raise RolePromotionPolicyError("foundation roles 1-3 boundary must define exclusions and out_of_scope rule")
    for band_name in ("9_5", "9_7"):
        band = dict(bands.get(band_name) or {})
        if float(band.get("minimum_pass_rate") or 0.0) <= 0.0:
            raise RolePromotionPolicyError(f"score band {band_name} requires minimum_pass_rate")
        if int(band.get("minimum_projects") or 0) <= 0:
            raise RolePromotionPolicyError(f"score band {band_name} requires minimum_projects")
        if not band.get("required_evidence"):
            raise RolePromotionPolicyError(f"score band {band_name} requires evidence")
    for role_id in ("project_analyzer", "architect", "spec_writer", "implementer"):
        role = dict(roles.get(role_id) or {})
        if float(role.get("target_score") or 0.0) < 9.7:
            raise RolePromotionPolicyError(f"{role_id} target_score must be at least 9.7")
        for field_name in ("required_checks", "required_semantic_checks", "growth_focus"):
            if not role.get(field_name):
                raise RolePromotionPolicyError(f"{role_id} missing {field_name}")
