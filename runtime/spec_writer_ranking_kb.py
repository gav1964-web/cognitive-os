"""Load and interpret Spec Writer ranking knowledge."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "spec_writer_ranking.json"


@lru_cache(maxsize=4)
def load_spec_writer_ranking_kb(path: str | None = None) -> dict[str, Any]:
    payload = json.loads((Path(path) if path else DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "spec_writer_ranking.v1":
        raise ValueError("Spec Writer ranking KB must use schema_version spec_writer_ranking.v1")
    adjustments = payload.get("adjustments")
    if not isinstance(adjustments, dict) or not adjustments:
        raise ValueError("Spec Writer ranking KB must define adjustments")
    for rule_id, row in adjustments.items():
        if not rule_id or not isinstance(row, dict) or not isinstance(row.get("score"), int) or not row.get("reason"):
            raise ValueError("Spec Writer adjustments require ids, integer scores, and reasons")
    for section in ("candidate_kind_scores", "candidate_level_scores", "formula", "provenance", "knowledge_leakage_audit"):
        if not isinstance(payload.get(section), dict):
            raise ValueError(f"Spec Writer ranking KB must define {section}")
    return payload


def adjustment(rule_id: str, **reason_values: object) -> tuple[int, str]:
    row = dict(load_spec_writer_ranking_kb()["adjustments"].get(rule_id) or {})
    if not row:
        raise KeyError(f"unknown Spec Writer ranking rule: {rule_id}")
    return int(row["score"]), str(row["reason"]).format(**reason_values)


def candidate_kind_adjustment(kind: str) -> tuple[int, str]:
    rows = load_spec_writer_ranking_kb()["candidate_kind_scores"]
    row = dict(rows.get(kind) or rows["default"])
    return int(row["score"]), str(row["reason"])


def candidate_level_score(level: str) -> int:
    return int(load_spec_writer_ranking_kb()["candidate_level_scores"].get(level, 0))


def project_candidate_score(value: object) -> int:
    formula = load_spec_writer_ranking_kb()["formula"]
    capped = min(int(value or 0), int(formula["project_score_cap"]))
    return capped // int(formula["project_score_divisor"])


def apply_rule(score: int, reasons: list[str], rule_id: str, **reason_values: object) -> int:
    delta, reason = adjustment(rule_id, **reason_values)
    reasons.append(reason)
    return score + delta


def knowledge_leakage_violations(root: Path) -> list[str]:
    audit = load_spec_writer_ranking_kb()["knowledge_leakage_audit"]
    patterns = [re.compile(str(value)) for value in audit.get("forbidden_patterns", [])]
    violations = []
    for relative in audit.get("paths", []):
        path = root / str(relative)
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{relative}:{line}: decision score must come from Spec Writer KB")
    return violations


def assert_no_knowledge_leakage(root: Path) -> None:
    violations = knowledge_leakage_violations(root)
    if violations:
        raise ValueError("; ".join(violations))
