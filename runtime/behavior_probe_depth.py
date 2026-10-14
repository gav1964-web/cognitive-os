"""Depth and source-evidence accounting for behavior probe cases."""

from __future__ import annotations

from typing import Any

from .source_unavailable_reason import count_source_unavailable_reason


def behavior_cases_depth(cases: list[dict[str, Any]]) -> dict[str, Any]:
    depth = {
        "http_probes": 0,
        "module_import_probes": 0,
        "manifest_probes": 0,
        "source_evidence_score": 0.0,
        "source_ok": 0,
        "source_stubbed": 0,
        "source_unavailable": 0,
    }
    stub_counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for case in cases:
        probe = dict(case.get("probe") or {})
        source = dict(case.get("source") or {})
        kind = str(probe.get("kind") or "")
        if kind in {"http", "module_import"}:
            depth[f"{kind}_probes"] += 1
            _add_source_depth(depth, stub_counts, reasons, source)
        elif kind == "capability_manifest":
            depth["manifest_probes"] += 1
    depth["source_dependency_stubs"] = dict(sorted(stub_counts.items()))
    depth["source_unavailable_reasons"] = reasons
    depth["source_evidence_score"] = round(float(depth["source_evidence_score"]), 3)
    return depth


def source_case_evidence(source: dict[str, Any]) -> float:
    stubs = {str(item) for item in source.get("dependency_stubs", [])}
    if not stubs:
        return 1.0
    if stubs == {"static_http_route_fallback"}:
        return 0.70
    return 0.65


def _add_source_depth(
    depth: dict[str, Any],
    stub_counts: dict[str, int],
    reasons: dict[str, int],
    source: dict[str, Any],
) -> None:
    if source.get("status") == "ok":
        depth["source_ok"] += 1
        depth["source_evidence_score"] += source_case_evidence(source)
        stubs = [str(item) for item in source.get("dependency_stubs", [])]
        if stubs:
            depth["source_stubbed"] += 1
            for stub in stubs:
                stub_counts[stub] = stub_counts.get(stub, 0) + 1
    else:
        depth["source_unavailable"] += 1
        count_source_unavailable_reason(reasons, source)
