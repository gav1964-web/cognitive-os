"""Owner API for pickle knowledge; read on every call to avoid stale KB caches."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'knowledge'
CATALOG_PATH = Path('plugins/exception_pickle/knowledge/exception_pickle_reconstruction_patterns.json')
DEFAULT_EXCEPTION_PICKLE_PATTERNS = KNOWLEDGE / 'exception_pickle_reconstruction_patterns.json'


def load_boundary_records() -> list[dict]:
    return json.loads((KNOWLEDGE / 'project_development_boundary_profiles.json').read_text(encoding='utf-8'))['profiles']


def load_source_contrast_records() -> list[dict]:
    return json.loads((KNOWLEDGE / 'project_development_source_contrasts.json').read_text(encoding='utf-8'))['contrasts']


def decorate_profile(profile: dict, *, active_patterns: dict | None = None) -> dict:
    active = load_exception_pickle_patterns() if active_patterns is None else active_patterns
    return _overlay(deepcopy(profile), active)


def load_exception_pickle_patterns(path: str | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_EXCEPTION_PICKLE_PATTERNS)
    if not source.exists():
        return validate_patterns_document(None)
    return validate_patterns_document(json.loads(source.read_text(encoding="utf-8")))


def validate_patterns_document(document: dict | None) -> dict[str, Any]:
    """Validate supplied data, without reading KB or granting activation authority."""
    if document is None:
        return {"schema_version": "exception_pickle_reconstruction_patterns.v1", "status": "absent"}
    if not isinstance(document, dict):
        raise ValueError('exception pickle pattern document must be an object')
    payload = deepcopy(document)
    if payload.get("schema_version") != "exception_pickle_reconstruction_patterns.v1":
        raise ValueError("exception pickle pattern schema mismatch")
    if payload.get("status") not in {"active", "absent"}:
        raise ValueError("invalid exception pickle pattern lifecycle")
    operator = dict(payload.get("operator") or {})
    if payload.get("status") == "active":
        required = {
            "id": "preserve_exception_constructor_reconstruction",
            "status": "validated_active",
            "hypothesis_kind": "exception_pickle_reconstruction_boundary",
            "reconstruction_method": "__reduce__",
            "state_strategy": "reuse_direct_assignments",
        }
        for field, expected in required.items():
            if operator.get(field) != expected:
                raise ValueError(
                    f"invalid exception pickle operator.{field}"
                )
        safety = dict(payload.get("safety") or {})
        if safety.get("source_apply_allowed") is not False or safety.get(
            "automatic_runtime_mutation_allowed"
        ) is not False:
            raise ValueError("unsafe exception pickle pattern policy")
    return payload


def _overlay(profile: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    if profile.get("id") != "exception_pickle_reconstruction_boundary":
        return profile
    operator = dict(active.get("operator") or {})
    if (
        active.get("status") != "active"
        or operator.get("status") != "validated_active"
        or operator.get("hypothesis_kind") != profile.get("id")
    ):
        return profile
    profile["status"] = "active"
    profile["active_kb_operator"] = operator
    evidence = dict(profile.get("evidence_state") or {})
    evidence.update({
        "promotion_ready": True,
        "promotion_authority": active.get("promotion_authority"),
        "active_catalog": "exception_pickle_reconstruction_patterns",
    })
    profile["evidence_state"] = evidence
    hypothesis = dict(profile.get("hypothesis") or {})
    hypothesis["status"] = "proposed"
    hypothesis["confidence"] = max(float(hypothesis.get("confidence") or 0.0), 0.97)
    profile["hypothesis"] = hypothesis
    return profile
