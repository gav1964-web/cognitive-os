"""Active AST-recognized semantic profiles admitted from project training."""

from __future__ import annotations

import ast
import json
import os
import tempfile
import textwrap
from functools import lru_cache
from pathlib import Path
from typing import Any

from .self_improvement_profile_families import recognize_contract_family


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json"
REQUIRED_FIELDS = ("id", "contract_family", "input_contract", "output_contract", "validation_gates", "failure_modes")


@lru_cache(maxsize=4)
def load_promoted_profiles(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "promoted_semantic_contract_profiles.v1":
        raise ValueError("promoted semantic contract profiles schema mismatch")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("promoted semantic contract profiles must contain profiles list")
    seen: set[str] = set()
    for value in profiles:
        profile = dict(value or {})
        if any(not profile.get(field) for field in REQUIRED_FIELDS):
            raise ValueError("promoted semantic contract profile lacks typed evidence")
        profile_id = str(profile["id"])
        if profile_id in seen or profile_id != str(profile["contract_family"]):
            raise ValueError(f"invalid promoted semantic contract profile id: {profile_id}")
        seen.add(profile_id)
        recognition = dict(profile.get("recognition_policy") or {})
        if recognition.get("source") != "python_ast" or recognition.get("recognizer") != profile_id:
            raise ValueError(f"invalid promoted recognition policy: {profile_id}")
        if int(profile.get("score_bonus") or 0) or int(profile.get("ranking_bonus") or 0):
            raise ValueError(f"numeric training bonus is forbidden: {profile_id}")
    return payload


def promoted_contract_for_candidate(candidate: dict[str, Any], *, path: str | None = None) -> dict[str, Any]:
    node = _function_node(str(candidate.get("snippet") or ""))
    if node is None:
        return {}
    recognized = recognize_contract_family(node)
    if recognized is None:
        return {}
    family_id, evidence = recognized
    profile = next(
        (dict(row) for row in load_promoted_profiles(path)["profiles"] if row.get("id") == family_id),
        None,
    )
    if profile is None:
        return {}
    required = set(dict(profile.get("recognition_policy") or {}).get("required_evidence") or [])
    if required and not all(evidence.get(key) for key in required):
        return {}
    return {
        **profile,
        "knowledge_profile": f"promoted:{family_id}",
        "training_evidence": evidence,
    }


def promote_profile(
    *, root: Path, profile: dict[str, Any], promotion_evidence: dict[str, Any]
) -> dict[str, Any]:
    path = root / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json"
    payload = load_promoted_profiles(str(path))
    family_id = str(profile.get("contract_family") or profile.get("id") or "")
    if any(str(row.get("id")) == family_id for row in payload["profiles"]):
        return {"status": "already_promoted", "profile_id": family_id, "path": path.as_posix()}
    record = {key: value for key, value in profile.items() if key not in {"training_summary", "effect_evidence"}}
    record.update({"id": family_id, "contract_family": family_id, "promotion_evidence": promotion_evidence})
    candidate = {**payload, "profiles": [*payload["profiles"], record]}
    candidate["profiles"].sort(key=lambda row: str(row.get("id") or ""))
    _validate_payload(candidate, path)
    _atomic_write(path, candidate)
    load_promoted_profiles.cache_clear()
    return {"status": "promoted", "profile_id": family_id, "path": path.as_posix()}


def _function_node(snippet: str) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    try:
        tree = ast.parse(textwrap.dedent(snippet))
    except SyntaxError:
        return None
    return next(
        (node for node in ast.walk(tree) if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))),
        None,
    )


def _validate_payload(payload: dict[str, Any], path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temporary = Path(handle.name)
    try:
        load_promoted_profiles.cache_clear()
        load_promoted_profiles(str(temporary))
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
