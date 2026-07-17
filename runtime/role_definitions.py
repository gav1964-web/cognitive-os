"""Load role definitions from external JSON schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROLE_DEFINITIONS_DIR = ROOT / "roles"
ROLE_RECORD_DEFAULTS_PATH = ROOT / "config" / "role_record_defaults.json"


@dataclass(frozen=True)
class RoleDefinition:
    role_id: str
    label: str
    order: int
    consumes: list[str]
    produces: list[str]
    kb_filters: dict[str, Any]
    policy: dict[str, Any]
    questions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "label": self.label,
            "order": self.order,
            "consumes": list(self.consumes),
            "produces": list(self.produces),
            "kb_filters": dict(self.kb_filters),
            "policy": dict(self.policy),
            "questions": [dict(row) for row in self.questions],
        }


@lru_cache(maxsize=1)
def load_role_definitions(path: str | None = None) -> list[RoleDefinition]:
    source = Path(path) if path else ROLE_DEFINITIONS_DIR
    if not source.exists():
        return []
    definitions = []
    for item in sorted(source.glob("*.json")):
        payload = json.loads(item.read_text(encoding="utf-8"))
        definitions.append(_parse_role_definition(payload, item))
    return sorted(definitions, key=lambda row: (row.order, row.role_id))


@lru_cache(maxsize=1)
def load_role_record_defaults(path: str | None = None) -> dict[str, list[str]]:
    source = Path(path) if path else ROLE_RECORD_DEFAULTS_PATH
    if not source.exists():
        return {}
    payload = json.loads(source.read_text(encoding="utf-8"))
    defaults = payload.get("record_type_defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("role record defaults must contain record_type_defaults object")
    role_set = set(role_ids())
    normalized: dict[str, list[str]] = {}
    for record_type, roles in defaults.items():
        if not isinstance(roles, list):
            raise ValueError(f"record defaults for {record_type} must be a list")
        normalized[str(record_type)] = [str(role) for role in roles if str(role) in role_set]
    return normalized


def role_ids() -> tuple[str, ...]:
    return tuple(row.role_id for row in load_role_definitions())


def role_definition_map() -> dict[str, RoleDefinition]:
    return {row.role_id: row for row in load_role_definitions()}


def role_question_count() -> int:
    counts = {len(row.questions) for row in load_role_definitions()}
    return counts.pop() if len(counts) == 1 else 0


def _parse_role_definition(payload: dict[str, Any], path: Path) -> RoleDefinition:
    if payload.get("schema_version") != "role_definition.v1":
        raise ValueError(f"{path.name} must use schema_version role_definition.v1")
    role_id = str(payload.get("role_id") or "").strip()
    if not role_id:
        raise ValueError(f"{path.name} requires role_id")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"{path.name} requires questions list")
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError(f"{path.name} contains non-object question")
        if not question.get("question") or not isinstance(question.get("answer"), dict):
            raise ValueError(f"{path.name} question requires question and answer")
    return RoleDefinition(
        role_id=role_id,
        label=str(payload.get("label") or role_id),
        order=int(payload.get("order") or 0),
        consumes=[str(item) for item in payload.get("consumes", [])],
        produces=[str(item) for item in payload.get("produces", [])],
        kb_filters=dict(payload.get("kb_filters") or {}),
        policy=dict(payload.get("policy") or {}),
        questions=questions,
    )
