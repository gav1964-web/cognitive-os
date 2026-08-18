"""Load and select anonymized deterministic function invocation patterns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "function_invocation_patterns.json"
_SCALARS = {"str", "string", "int", "integer", "float", "number", "bool", "boolean"}
_COLLECTIONS = {"list", "array", "sequence", "tuple", "set"}
_MAPPINGS = {"dict", "mapping", "object"}


def load_function_invocation_patterns(path: str | Path | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "function_invocation_patterns.v1":
        raise ValueError("Unsupported function invocation patterns schema")
    policy = dict(payload.get("admission_policy") or {})
    if policy.get("automatic_promotion_allowed") is not False:
        raise ValueError("Invocation patterns cannot permit automatic promotion")
    if policy.get("store_project_names") is not False or policy.get("store_source_code") is not False:
        raise ValueError("Invocation pattern KB must remain anonymized")
    min_projects = int(policy.get("minimum_distinct_projects") or 0)
    min_observations = int(policy.get("minimum_observations") or 0)
    for row in [dict(item) for item in list(payload.get("patterns") or [])]:
        if not all(row.get(key) for key in ("id", "input_shape", "construction", "call_style", "oracle")):
            raise ValueError("Invocation pattern is incomplete")
        evidence = dict(row.get("evidence") or {})
        if int(evidence.get("distinct_projects") or 0) < min_projects:
            raise ValueError(f"Invocation pattern lacks independent-project evidence: {row.get('id')}")
        if int(evidence.get("observations") or 0) < min_observations:
            raise ValueError(f"Invocation pattern lacks observation evidence: {row.get('id')}")
    return payload


def match_invocation_pattern(
    input_contract: dict[str, Any], output_contract: dict[str, Any], catalog: dict[str, Any] | None = None
) -> dict[str, str]:
    shape = _input_shape(input_contract)
    payload = catalog or load_function_invocation_patterns()
    for row in [dict(item) for item in list(payload.get("patterns") or [])]:
        if row.get("input_shape") == shape:
            return {key: str(row[key]) for key in ("id", "construction", "call_style", "oracle")}
    return {
        "id": "unknown_contract",
        "construction": "llm_or_human_fallback",
        "call_style": "unresolved",
        "oracle": "unresolved",
    }


def _input_shape(contract: dict[str, Any]) -> str:
    kinds = {_type_kind(value) for value in contract.values()}
    if kinds and kinds <= {"scalar"}:
        return "scalar_fields"
    if kinds and kinds <= {"collection"}:
        return "collection_fields"
    if kinds and kinds <= {"mapping"}:
        return "mapping_fields"
    if "model" in kinds:
        return "declared_model_fields"
    return "scalar_fields" if not kinds else "unknown"


def _type_kind(value: Any) -> str:
    compact = str(value).lower().replace(" ", "")
    base = compact.split("[", 1)[0]
    if base in _SCALARS:
        return "scalar"
    if base in _COLLECTIONS:
        return "collection"
    if base in _MAPPINGS:
        return "mapping"
    if compact.startswith(("optional[", "union[")):
        return _type_kind(compact.split("[", 1)[1].split(",", 1)[0].rstrip("]"))
    return "model" if compact and not compact.startswith("inferred") else "unknown"
