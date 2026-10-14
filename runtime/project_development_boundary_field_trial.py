"""Evaluate staged boundary profiles on a frozen source-backed corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .project_development_boundary_interpreter import interpret_boundary
from .project_development_source_evidence import collect_python_target_facts


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmark_corpora" / "project_development_boundaries"


def run_boundary_field_trial(
    corpus_dir: Path | None = None, *, split: str | None = None
) -> dict[str, Any]:
    root = (corpus_dir or DEFAULT_CORPUS).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "project_development_boundary_corpus.v1":
        raise ValueError("project development boundary corpus schema mismatch")
    selected = [
        dict(row) for row in manifest.get("cases") or []
        if split is None or row.get("split") == split
    ]
    cases = []
    for row in selected:
        target = f"{row['path']}:{row['target']}"
        facts = collect_python_target_facts(root, target)
        profile = interpret_boundary({
            "feedback": {"reason": "no_unique_development_helper_extraction"},
            "source_facts": facts,
            "reducer_attempts": [{
                "operation_kind": "extract_append_mapping_helper",
                "reason": "append_mapping_helper_pattern_not_proven",
            }],
        })
        actual = str(profile.get("hypothesis_kind") or profile.get("id") or "")
        expected = str(row.get("expected_profile") or "")
        cases.append({
            "case_id": row.get("id"),
            "split": row.get("split"),
            "lineage": row.get("lineage"),
            "target": target,
            "source_facts": facts,
            "expected_profile": expected,
            "actual_profile": actual,
            "matched": actual == expected,
            "knowledge_status": profile.get("status"),
        })
    passed = sum(row["matched"] for row in cases)
    blind = [row for row in cases if row["split"] == "blind"]
    lineages = {str(row["lineage"]) for row in cases}
    return {
        "artifact_type": "ProjectDevelopmentBoundaryFieldTrialReport",
        "schema_version": "project_development_boundary_field_trial_report.v1",
        "status": "passed" if cases and passed == len(cases) else "failed",
        "split": split or "all",
        "summary": {
            "case_count": len(cases),
            "passed": passed,
            "accuracy": round(passed / len(cases), 4) if cases else 0.0,
            "blind_case_count": len(blind),
            "independent_lineage_count": len(lineages),
        },
        "promotion": {
            "status": "not_promoted",
            "kb_promotion_evidence": False,
            "reason": "field_accuracy_does_not_replace_multi_report_promotion_gate",
        },
        "cases": cases,
    }
