"""AST-only audit of repeated mixed-effect recovery opportunities."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .recovery_pattern_ast import (
    call_name as _call_name,
    called_names as _called_names,
    effects as _effects,
    has_dynamic_subprocess_arguments as _has_dynamic_subprocess_arguments,
    has_request_mapping as _has_request_mapping,
    has_return_mapping as _has_return_mapping,
    import_aliases as _import_aliases,
    module_findings as _module_findings,
    pattern_clusters as _pattern_clusters,
    python_files as _python_files,
    structural_fingerprint as _structural_fingerprint,
    transforms as _transforms,
)
from .recovery_pattern_clusters import (
    CLUSTER_STRATEGIES,
    clusters as _clusters,
    execution_lanes as _execution_lanes,
    implemented_clusters as _implemented_clusters,
    recommendation as _recommendation,
    research_backlog as _research_backlog,
    research_question as _research_question,
)


def run_recovery_pattern_audit(
    root: Path,
    *,
    corpus_roots: list[Path],
    max_files: int = 2500,
    write: bool = False,
) -> dict[str, Any]:
    findings, scanned, parse_failures = _scan_corpora(corpus_roots, max_files=max_files)
    clusters = _clusters(findings, _implemented_clusters())
    unresolved = [row for row in findings if row["resolved_by_pure_helper"] is False]
    report = {
        "artifact_type": "RecoveryPatternAuditReport",
        "schema_version": "recovery_pattern_audit.v1",
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "corpus_roots": [path.as_posix() for path in corpus_roots],
            "max_files": max_files,
            "scanned_python_files": scanned,
            "parse_failures": parse_failures,
        },
        "summary": {
            "mixed_effect_function_count": len({row["source"] for row in findings}),
            "pattern_finding_count": len(findings),
            "resolved_by_pure_helper_count": sum(row["resolved_by_pure_helper"] for row in findings),
            "unresolved_count": len(unresolved),
            "cluster_count": len(clusters),
        },
        "clusters": clusters,
        "findings": findings,
        "recommendation": _recommendation(clusters),
        "execution_lanes": _execution_lanes(clusters),
        "research_backlog": _research_backlog(clusters),
        "policy": {
            "ast_only": True,
            "project_imports_forbidden": True,
            "source_mutation": False,
            "minimum_repetition_for_recipe": 2,
        },
    }
    if write:
        _write_report(root, report)
    return report


def _scan_corpora(corpus_roots: list[Path], *, max_files: int) -> tuple[list[dict[str, Any]], int, int]:
    findings: list[dict[str, Any]] = []
    scanned = 0
    parse_failures = 0
    for corpus in corpus_roots:
        if not corpus.is_dir() or scanned >= max_files:
            continue
        for path in _python_files(corpus):
            if scanned >= max_files:
                break
            scanned += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError):
                parse_failures += 1
                continue
            findings.extend(_module_findings(path, corpus, tree))
    return findings, scanned, parse_failures


def _write_report(root: Path, report: dict[str, Any]) -> None:
    out = root / "artifacts" / "field_trials"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out / f"recovery_pattern_audit_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = path.as_posix()
