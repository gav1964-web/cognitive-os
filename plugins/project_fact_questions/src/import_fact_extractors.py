"""Config-driven import/effect fact extractors for Python structure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXTRACTORS_PATH = ROOT / "config" / "project_import_fact_extractors.json"


def import_fact_answers(
    python_structure: dict[str, Any], allowed_paths: set[str] | None
) -> dict[str, dict[str, Any]]:
    payload = load_import_fact_extractors()
    answers: dict[str, dict[str, Any]] = {}
    for extractor in payload.get("extractors", []):
        if not isinstance(extractor, dict):
            continue
        answer_key = str(extractor.get("answer_key") or "")
        rows = _matching_files(extractor, python_structure, allowed_paths)
        answers[answer_key] = {"count": len(rows), "files": rows}
    return answers


def load_import_fact_extractors() -> dict[str, Any]:
    payload = json.loads(EXTRACTORS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_import_fact_extractors.v1":
        raise ValueError("project import fact extractors schema mismatch")
    if payload.get("status") != "active":
        raise ValueError("project import fact extractors must be active")
    return payload


def _matching_files(
    extractor: dict[str, Any], python_structure: dict[str, Any], allowed_paths: set[str] | None
) -> list[dict[str, Any]]:
    rows = []
    import_roots = {str(item).lower() for item in extractor.get("import_roots_any", [])}
    side_effects = {str(item) for item in extractor.get("side_effects_any", [])}
    for file_row in python_structure.get("files", []):
        if not isinstance(file_row, dict):
            continue
        path = str(file_row.get("path") or "")
        if allowed_paths is not None and path not in allowed_paths:
            continue
        evidence = _import_evidence(file_row, import_roots)
        evidence.extend(_effect_evidence(file_row, side_effects))
        if evidence:
            rows.append({"path": path, "evidence": sorted(set(evidence))})
    return sorted(rows, key=lambda row: str(row["path"]))


def _import_evidence(file_row: dict[str, Any], import_roots: set[str]) -> list[str]:
    imports = {str(item).split(".", 1)[0].lower() for item in file_row.get("imports", [])}
    return [f"import:{item}" for item in sorted(imports & import_roots)]


def _effect_evidence(file_row: dict[str, Any], side_effects: set[str]) -> list[str]:
    evidence = []
    for function in file_row.get("functions", []):
        if not isinstance(function, dict):
            continue
        matched = set(function.get("side_effects", []) or []) & side_effects
        if matched:
            evidence.append(f"function:{function.get('name')}:{','.join(sorted(matched))}")
    return evidence
