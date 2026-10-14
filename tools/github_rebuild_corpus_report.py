"""Scoring and report helpers for GitHub rebuild corpus runs."""

from __future__ import annotations

from typing import Any

from runtime.behavior_probe_depth import behavior_cases_depth


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row.get("status") == "ok"]
    needs = [row for row in rows if row.get("status") == "needs_work"]
    failed = [row for row in rows if row.get("status") not in {"ok", "needs_work"}]
    probes = sum(int(dict(row.get("behavior_summary") or {}).get("total") or 0) for row in rows)
    probe_failed = sum(int(dict(row.get("behavior_summary") or {}).get("failed") or 0) for row in rows)
    http = sum(int(dict(row.get("behavior_depth") or {}).get("http_probes") or 0) for row in rows)
    module_import = sum(int(dict(row.get("behavior_depth") or {}).get("module_import_probes") or 0) for row in rows)
    manifest = sum(int(dict(row.get("behavior_depth") or {}).get("manifest_probes") or 0) for row in rows)
    source_ok = sum(int(dict(row.get("behavior_depth") or {}).get("source_ok") or 0) for row in rows)
    source_stubbed = sum(int(dict(row.get("behavior_depth") or {}).get("source_stubbed") or 0) for row in rows)
    source_evidence = sum(float(dict(row.get("behavior_depth") or {}).get("source_evidence_score") or 0) for row in rows)
    source_unavailable = sum(int(dict(row.get("behavior_depth") or {}).get("source_unavailable") or 0) for row in rows)
    dependency_stubs = _merge_depth_counts(rows, "source_dependency_stubs")
    unavailable_reasons = _merge_reason_counts(rows)
    blocked_env = [row for row in rows if row.get("probe_env_status") == "blocked"]
    prepared_env = [
        row
        for row in rows
        if any(dict(run).get("status") == "prepared" for run in list(row.get("probe_env_prepare_runs") or []))
        or dict(row.get("probe_env_prepare") or {}).get("status") == "prepared"
    ]
    missing_modules = sorted({str(module) for row in rows for module in row.get("missing_modules", [])})
    verdicts: dict[str, int] = {}
    for row in rows:
        verdict = str(row.get("corpus_verdict") or "unknown")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    averages = _average_quality(rows)
    conservative_scores = [
        float(dict(row.get("quality") or {}).get("conservative_score") or 0)
        for row in rows
    ]
    return {
        "ok": len(ok),
        "needs_work": len(needs),
        "failed": len(failed),
        "behavior_probes": probes,
        "behavior_probe_failed": probe_failed,
        "http_probes": http,
        "module_import_probes": module_import,
        "manifest_probes": manifest,
        "source_ok": source_ok,
        "source_stubbed": source_stubbed,
        "source_dependency_stubs": dependency_stubs,
        "source_evidence_score": round(source_evidence, 3),
        "source_unavailable": source_unavailable,
        "source_unavailable_reasons": unavailable_reasons,
        "probe_env_blocked": len(blocked_env),
        "probe_env_prepared": len(prepared_env),
        "missing_modules": missing_modules,
        "blueprints": sum(int(row.get("behavior_blueprints") or 0) for row in rows),
        "average_score": round(sum(conservative_scores) / len(conservative_scores), 3) if conservative_scores else 0,
        "legacy_average_score": round(sum(float(row.get("legacy_score", row.get("score")) or 0) for row in rows) / len(rows), 3) if rows else 0,
        "worst_score": round(min(conservative_scores), 3) if conservative_scores else 0,
        "average_quality": averages,
        "verdicts": verdicts,
    }


def _quality_scores(trial: dict[str, Any], comparison: dict[str, Any], depth: dict[str, Any]) -> dict[str, float]:
    spec = dict(trial.get("spec") or {})
    checks = dict(comparison.get("checks") or {})
    analysis_parts = [
        bool(spec.get("main_task")),
        bool(spec.get("entrypoints")),
        bool(spec.get("supported_scenarios")),
        bool(spec.get("core_capabilities") or spec.get("routes")),
    ]
    spec_parts = [
        bool(spec.get("artifact_type") == "ProjectRebuildSpec"),
        bool(spec.get("target_name")),
        bool(spec.get("quality_targets")),
        bool(spec.get("routes") or spec.get("core_capabilities")),
    ]
    scaffold_keys = ["has_app_entrypoint", "has_readme", "has_contract_tests", "compiles", "contract_tests_pass"]
    scaffold_parts = [checks.get(key) is True for key in scaffold_keys]
    http = int(depth.get("http_probes") or 0)
    module_import = int(depth.get("module_import_probes") or 0)
    manifest = int(depth.get("manifest_probes") or 0)
    source_ok = int(depth.get("source_ok") or 0)
    source_stubbed = int(depth.get("source_stubbed") or 0)
    executable = http + module_import
    behavior = dict(comparison.get("behavior") or {})
    behavior_summary = dict(behavior.get("summary") or {})
    case_total = int(behavior_summary.get("total") or 0)
    case_passed = int(behavior_summary.get("passed") or 0)
    pass_ratio = case_passed / case_total if case_total else 0.0
    if executable:
        if "source_evidence_score" in depth:
            source_evidence = float(depth.get("source_evidence_score") or 0) / executable
        else:
            source_full = max(0, source_ok - source_stubbed)
            source_evidence = (source_full + source_stubbed * 0.65) / executable
        behavior_score = min(source_evidence, pass_ratio)
    elif manifest:
        behavior_score = min(0.35, pass_ratio) if case_total else 0.35
    else:
        behavior_score = 0.0
    analysis_score = _ratio(analysis_parts)
    spec_score = _ratio(spec_parts)
    scaffold_score = _ratio(scaffold_parts)
    layer_floor = min(analysis_score, spec_score, scaffold_score, behavior_score)
    unavailable = int(depth.get("source_unavailable") or 0)
    total_source = source_ok + unavailable
    unavailable_penalty = 0.0
    if total_source:
        unavailable_penalty = min(0.25, unavailable / total_source * 0.25)
    conservative_score = max(0.0, layer_floor - unavailable_penalty)
    mean_score = round((analysis_score + spec_score + scaffold_score + behavior_score) / 4, 3)
    return {
        "analysis_score": analysis_score,
        "spec_score": spec_score,
        "scaffold_score": scaffold_score,
        "behavior_score": round(behavior_score, 3),
        "mean_score": mean_score,
        "conservative_score": round(conservative_score, 3),
        "confidence": round(conservative_score, 3),
    }


def _corpus_verdict(quality: dict[str, float]) -> str:
    behavior = float(quality.get("behavior_score") or 0)
    conservative = float(quality.get("conservative_score") or quality.get("confidence") or 0)
    if behavior <= 0:
        return "needs_review"
    if conservative < 0.75:
        return "needs_review"
    if behavior < 0.8:
        return "behavior_incomplete"
    if conservative >= 0.85:
        return "behavior_checked"
    return "shape_checked"


def _average_quality(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ["analysis_score", "spec_score", "scaffold_score", "behavior_score", "mean_score", "conservative_score", "confidence"]
    if not rows:
        return {key: 0.0 for key in keys}
    return {
        key: round(sum(float(dict(row.get("quality") or {}).get(key) or 0) for row in rows) / len(rows), 3)
        for key in keys
    }


def _ratio(parts: list[bool]) -> float:
    return round(sum(1 for item in parts if item) / len(parts), 3) if parts else 0.0


def _merge_reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return _merge_depth_counts(rows, "source_unavailable_reasons")


def _merge_depth_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    merged: dict[str, int] = {}
    for row in rows:
        counts = dict(dict(row.get("behavior_depth") or {}).get(key) or {})
        for name, value in counts.items():
            merged[str(name)] = merged.get(str(name), 0) + int(value or 0)
    return dict(sorted(merged.items()))


def _behavior_depth(behavior: dict[str, Any]) -> dict[str, Any]:
    return behavior_cases_depth(list(behavior.get("cases", [])))


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# GitHub Rebuild Corpus", "", f"- Status: `{report['status']}`", f"- Projects: `{report['repo_count']}`"]
    summary = dict(report.get("summary", {}))
    lines.extend(
        [
            f"- OK: `{summary.get('ok')}`",
            f"- Needs work: `{summary.get('needs_work')}`",
            f"- Behavior probes: `{summary.get('behavior_probes')}` / failed `{summary.get('behavior_probe_failed')}`",
            f"- HTTP probes: `{summary.get('http_probes')}`",
            f"- Module import probes: `{summary.get('module_import_probes')}`",
            f"- Manifest probes: `{summary.get('manifest_probes')}`",
            f"- Source executed: `{summary.get('source_ok')}` / unavailable `{summary.get('source_unavailable')}`",
            f"- Source dependency-stubbed: `{summary.get('source_stubbed')}`",
            f"- Source dependency stubs: `{summary.get('source_dependency_stubs')}`",
            f"- Probe env blocked: `{summary.get('probe_env_blocked')}`",
            f"- Probe env prepared: `{summary.get('probe_env_prepared')}`",
            f"- Missing modules: `{', '.join(summary.get('missing_modules') or [])}`",
            f"- Blueprints: `{summary.get('blueprints')}`",
            f"- Verdicts: `{summary.get('verdicts')}`",
            f"- Conservative score: avg `{summary.get('average_score')}` / worst `{summary.get('worst_score')}`",
            f"- Legacy average score: `{summary.get('legacy_average_score')}`",
            f"- Average quality: `{summary.get('average_quality')}`",
            "",
            "| Repo | Verdict | Floor | Mean | A/S/R/B | Probes | HTTP | Src OK | Missing |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report.get("results", []):
        behavior = dict(row.get("behavior_summary") or {})
        depth = dict(row.get("behavior_depth") or {})
        quality = dict(row.get("quality") or {})
        probes = f"{behavior.get('passed', 0)}/{behavior.get('total', 0)}"
        missing = ", ".join(str(item) for item in row.get("missing", []))
        quartet = (
            f"{quality.get('analysis_score', 0)}/"
            f"{quality.get('spec_score', 0)}/"
            f"{quality.get('scaffold_score', 0)}/"
            f"{quality.get('behavior_score', 0)}"
        )
        lines.append(
            f"| `{row.get('repo')}` | `{row.get('corpus_verdict')}` | `{quality.get('conservative_score')}` | `{quality.get('mean_score')}` | `{quartet}` | "
            f"`{probes}` | `{depth.get('http_probes', 0)}` | `{depth.get('source_ok', 0)}` | {missing} |"
        )
    return "\n".join(lines) + "\n"
