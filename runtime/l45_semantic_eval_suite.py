"""Multi-profile evaluation harness for L4.5 semantic routing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .l45_semantic_analytics import analyze_l45_semantic_benchmark, build_l45_risk_policy_gap_report
from .l45_semantic_benchmark import run_l45_semantic_benchmark
from .l45_semantic_comparison import compare_l45_semantic_reports


DEFAULT_PROFILES = ["balanced", "risk_heavy", "unknown_template_heavy", "known_template_regression"]


def run_l45_semantic_evaluation_suite(
    *,
    root: Path,
    generated_corpus_size: int = 50,
    seed: int = 45,
    profiles: list[str] | None = None,
    include_model: bool = False,
    model_quality_mode: str = "model_propose_only",
    config: Any = None,
    write: bool = False,
) -> dict[str, Any]:
    """Run deterministic and optional model-backed L4.5 benchmark profiles."""

    selected_profiles = profiles or list(DEFAULT_PROFILES)
    profile_reports = [
        _run_profile(
            root=root,
            profile=profile,
            generated_corpus_size=generated_corpus_size,
            seed=seed,
            include_model=include_model,
            model_quality_mode=model_quality_mode,
            config=config,
            write=write,
        )
        for profile in selected_profiles
    ]
    failed_profiles = [
        row["profile"]
        for row in profile_reports
        if row["deterministic"]["status"] != "ok"
        or row["risk_policy_gap"]["summary"]["gap_count"] != 0
        or (row.get("model") and row["model"]["status"] != "ok")
    ]
    report = {
        "artifact_type": "L45SemanticEvaluationSuiteReport",
        "status": "ok" if not failed_profiles else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "generated_corpus_size": generated_corpus_size,
            "seed": seed,
            "profiles": selected_profiles,
            "include_model": include_model,
            "model_quality_mode": model_quality_mode if include_model else None,
        },
        "summary": {
            "profile_count": len(profile_reports),
            "failed_profiles": failed_profiles,
            "deterministic_passed": sum(1 for row in profile_reports if row["deterministic"]["status"] == "ok"),
            "risk_policy_gap_count": sum(
                int(row["risk_policy_gap"]["summary"]["gap_count"]) for row in profile_reports
            ),
            "model_passed": sum(
                1 for row in profile_reports if row.get("model") and row["model"]["status"] == "ok"
            ),
            "model_better": sum(
                int(dict(row.get("comparison", {}).get("summary", {})).get("model_better") or 0)
                for row in profile_reports
            ),
            "deterministic_better": sum(
                int(dict(row.get("comparison", {}).get("summary", {})).get("deterministic_better") or 0)
                for row in profile_reports
            ),
            "model_fallbacks": sum(
                int(dict(row.get("comparison", {}).get("summary", {})).get("model_fallback_count") or 0)
                for row in profile_reports
            ),
        },
        "profiles": profile_reports,
    }
    report["summary"]["verdict"] = _suite_verdict(report["summary"], include_model=include_model)
    if write:
        out_dir = root / "artifacts" / "l45_semantic_benchmark"
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = "model" if include_model else "deterministic"
        path = out_dir / f"l45_semantic_evaluation_suite_{suffix}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _run_profile(
    *,
    root: Path,
    profile: str,
    generated_corpus_size: int,
    seed: int,
    include_model: bool,
    model_quality_mode: str,
    config: Any,
    write: bool,
) -> dict[str, Any]:
    deterministic = run_l45_semantic_benchmark(
        root=root,
        generated_corpus_size=generated_corpus_size,
        seed=seed,
        corpus_profile=profile,
        write=write,
    )
    analytics_path = (
        root
        / "artifacts"
        / "l45_semantic_benchmark"
        / f"l45_semantic_benchmark_deterministic_generated_{profile}_analytics.json"
        if write
        else None
    )
    gap_path = (
        root
        / "artifacts"
        / "l45_semantic_benchmark"
        / f"l45_semantic_benchmark_deterministic_generated_{profile}_policy_gap.json"
        if write
        else None
    )
    analytics = analyze_l45_semantic_benchmark(deterministic, write_path=analytics_path)
    risk_gap = build_l45_risk_policy_gap_report(deterministic, write_path=gap_path)
    row: dict[str, Any] = {
        "profile": profile,
        "deterministic": _benchmark_summary(deterministic),
        "analytics": _analytics_summary(analytics),
        "risk_policy_gap": _gap_summary(risk_gap),
    }
    if include_model:
        model = run_l45_semantic_benchmark(
            root=root,
            generated_corpus_size=generated_corpus_size,
            seed=seed,
            corpus_profile=profile,
            use_model=True,
            model_quality_mode=model_quality_mode,
            config=config,
            write=write,
        )
        comparison_path = (
            root
            / "artifacts"
            / "l45_semantic_benchmark"
            / f"l45_semantic_comparison_generated_{profile}.json"
            if write
            else None
        )
        comparison = compare_l45_semantic_reports(
            deterministic_report=deterministic,
            model_report=model,
            write_path=comparison_path,
        )
        row["model"] = _benchmark_summary(model)
        row["comparison"] = {
            "status": comparison["status"],
            "summary": dict(comparison["summary"]),
            "interpretation": dict(comparison["interpretation"]),
            "report_path": comparison.get("report_path"),
        }
    return row


def _benchmark_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "model_quality_mode": report.get("model_quality_mode"),
        "corpus": dict(report.get("corpus", {})) if isinstance(report.get("corpus"), dict) else {},
        "summary": dict(report.get("summary", {})) if isinstance(report.get("summary"), dict) else {},
        "report_path": report.get("report_path"),
    }


def _analytics_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "summary": dict(report.get("summary", {})) if isinstance(report.get("summary"), dict) else {},
        "boundary_counts": dict(report.get("boundary_counts", {})) if isinstance(report.get("boundary_counts"), dict) else {},
        "action_counts": dict(report.get("action_counts", {})) if isinstance(report.get("action_counts"), dict) else {},
        "category_counts": dict(report.get("category_counts", {})) if isinstance(report.get("category_counts"), dict) else {},
        "policy_signals": dict(report.get("policy_signals", {})) if isinstance(report.get("policy_signals"), dict) else {},
        "report_path": report.get("report_path"),
    }


def _gap_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"),
        "summary": dict(report.get("summary", {})) if isinstance(report.get("summary"), dict) else {},
        "report_path": report.get("report_path"),
    }


def _suite_verdict(summary: dict[str, Any], *, include_model: bool) -> str:
    if int(summary.get("risk_policy_gap_count") or 0) > 0:
        return "risk_policy_regression"
    if not include_model:
        return "deterministic_profiles_pass"
    if int(summary.get("model_fallbacks") or 0) > 0:
        return "model_provider_degraded"
    if int(summary.get("model_better") or 0) > int(summary.get("deterministic_better") or 0):
        return "model_adds_signal"
    if int(summary.get("deterministic_better") or 0) > 0:
        return "model_underperformed_deterministic_route"
    return "model_matches_deterministic_without_advantage"
