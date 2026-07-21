"""Advisory coverage report for external configuration catalogs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .l4_decision_table import load_l4_decision_rules
from .operation_recipe_rules import load_operation_recipe_rules
from .sandbox_programmer_profiles import load_sandbox_programmer_profiles
from .semantic_resolution_rules import load_semantic_resolution_rules
from .stage2_template_routes import load_stage2_template_routes


ROOT = Path(__file__).resolve().parents[1]


def build_config_coverage_report(root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT).resolve()
    haystack = _collect_text(base)
    sections = [
        _coverage_section(
            "stage2_templates",
            [str(item) for item in load_stage2_template_routes(str(base / "config" / "stage2_template_routes.json")).get("known_templates", [])],
            haystack,
        ),
        _coverage_section(
            "operation_transforms",
            [str(item) for item in load_operation_recipe_rules(str(base / "config" / "operation_recipe_rules.json")).get("allowed_transforms", [])],
            haystack,
        ),
        _coverage_section(
            "sandbox_programmer_profiles",
            list(dict(load_sandbox_programmer_profiles(str(base / "config" / "sandbox_programmer_profiles.json")).get("profiles") or {})),
            haystack,
        ),
        _coverage_section(
            "semantic_resolution_rules",
            [str(row.get("rule_id") or "") for row in load_semantic_resolution_rules(str(base / "config" / "semantic_resolution_rules.json")).get("existing_resolution_rules", [])],
            haystack,
        ),
        _coverage_section(
            "l4_decision_rules",
            [str(row.get("rule_id") or "") for row in load_l4_decision_rules(str(base / "config" / "l4_decision_rules.json")).get("rules", [])],
            haystack,
        ),
    ]
    return {
        "artifact_type": "ConfigCoverageReport",
        "status": "ok",
        "root": base.as_posix(),
        "scope": ["tests", "registry/local_automation_mvp_cases.json", "registry/sandbox_programmer_operations.json"],
        "sections": sections,
        "summary": {
            "entities": sum(section["total"] for section in sections),
            "covered": sum(section["covered"] for section in sections),
            "uncovered": sum(len(section["uncovered"]) for section in sections),
        },
    }


def _coverage_section(name: str, ids: list[str], haystack: str) -> dict[str, Any]:
    unique = sorted({item for item in ids if item})
    covered = [item for item in unique if item in haystack]
    return {
        "name": name,
        "total": len(unique),
        "covered": len(covered),
        "coverage": round(len(covered) / len(unique), 3) if unique else 1.0,
        "uncovered": [item for item in unique if item not in set(covered)],
    }


def _collect_text(root: Path) -> str:
    chunks: list[str] = []
    for folder in (root / "tests",):
        if folder.is_dir():
            for path in folder.rglob("*.py"):
                chunks.append(_safe_read(path))
    for path in (
        root / "registry" / "local_automation_mvp_cases.json",
        root / "registry" / "sandbox_programmer_operations.json",
        root / "registry" / "sandbox_programmer_compositions.json",
    ):
        if path.is_file():
            chunks.append(_safe_read(path))
    return "\n".join(chunks)


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
