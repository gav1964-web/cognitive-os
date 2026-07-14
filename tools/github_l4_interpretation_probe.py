"""Run external Level 4 project interpretation over GitHub benchmark projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.l4_defaults import DEFAULT_L4_BASE_URL, DEFAULT_L4_MODEL
from runtime.local_inference import LocalInferenceConfig
from runtime.project_benchmark import analyze_project
from runtime.project_deliberation import deliberate_project_report
from runtime.project_l4_quality import score_l4_interpretation
from runtime.project_signals import generate_project_signals


LOCAL_L4_FORBIDDEN_MODELS = {
    "local",
    "qwen-local",
    "qwen-local-cpu",
    "fast-local-cpu",
    "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_l4_interpretation_probe")
    parser.add_argument("--l4-base-url", default=DEFAULT_L4_BASE_URL)
    parser.add_argument("--l4-model", default=DEFAULT_L4_MODEL)
    parser.add_argument("--l4-timeout", type=float, default=180.0)
    parser.add_argument("--context", choices=["expanded", "compact"], default="expanded")
    parser.add_argument("--no-response-format", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.l4_model in LOCAL_L4_FORBIDDEN_MODELS:
        print(json.dumps({"status": "failed", "error": "L4 must use an external model name"}, ensure_ascii=False))
        return 2
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        l4_base_url=args.l4_base_url.rstrip("/"),
        l4_model=args.l4_model,
        l4_timeout=args.l4_timeout,
        context_mode=args.context,
        response_format=not args.no_response_format,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(
    *,
    root: Path,
    projects_dir: Path,
    label: str,
    l4_base_url: str,
    l4_model: str,
    l4_timeout: float,
    context_mode: str,
    response_format: bool,
) -> dict[str, Any]:
    telemetry: list[dict[str, Any]] = []
    config = LocalInferenceConfig(
        base_url=l4_base_url,
        model=l4_model,
        timeout_seconds=l4_timeout,
        response_format=response_format,
        provider_label="external_l4",
        telemetry_sink=telemetry.append,
    )
    cases = [_run_case(project_dir, config, context_mode, telemetry=telemetry) for project_dir in _project_dirs(projects_dir)]
    return {
        "status": "ok" if all(case["status"] == "ok" for case in cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "provider": {"base_url": l4_base_url, "model": l4_model, "context_mode": context_mode},
        "summary": _summary(cases),
        "invariants": {
            "l35_llm_invoked": False,
            "l4_local_models_forbidden": True,
            "source_projects_modified": any(case["source_code_changes"] for case in cases),
            "external_projects_are_read_only": True,
        },
        "cases": cases,
    }


def _run_case(
    project_dir: Path,
    config: LocalInferenceConfig,
    context_mode: str,
    *,
    telemetry: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    telemetry_start = len(telemetry or [])
    source_before = _git_snapshot(project_dir)
    outputs = analyze_project(project_dir)
    goal_report = {
        "goal_id": f"github_l4_{project_dir.name}",
        "goal": f"Interpret project architecture for {project_dir.name}",
        "execution": {"status": "ok", "completed_nodes": list(outputs), "outputs": outputs},
    }
    signals = generate_project_signals(goal_report, config=_disabled_l35_config())
    interpretation = deliberate_project_report(
        goal_report,
        level35_signals=signals,
        config=config,
        context_mode=context_mode,
    )
    quality = score_l4_interpretation(interpretation)
    checks = _quality_checks(interpretation)
    hardening_actions = list(interpretation.get("quality_warnings", []))
    source = str(interpretation.get("source") or "")
    status = "ok" if all(checks.values()) and quality["passed"] and source == "external_l4" else "needs_review"
    inference_calls = list((telemetry or [])[telemetry_start:])
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": status,
        "checks": checks,
        "quality": quality,
        "hardening_actions": hardening_actions,
        "model_output_clean": not hardening_actions,
        "l4_source": source,
        "l4_model": interpretation.get("model"),
        "context_mode": interpretation.get("context_mode"),
        "confidence": interpretation.get("confidence"),
        "executive_summary": interpretation.get("executive_summary"),
        "capability_decomposition": interpretation.get("capability_decomposition", [])[:3],
        "refactor_plan": interpretation.get("refactor_plan", [])[:3],
        "open_questions": interpretation.get("open_questions", [])[:3],
        "fallback_reason": interpretation.get("fallback_reason"),
        "signal_source": signals.get("source"),
        "signal_count": len(signals.get("signals", [])),
        "source_code_changes": _source_changed(source_before, _git_snapshot(project_dir)),
        "source_snapshot_available": source_before is not None,
        "inference": _case_inference(inference_calls),
    }


def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = report_dir / f"{label}_{stamp}.json"
    md_path = report_dir / f"{label}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}


def _project_dirs(projects_dir: Path) -> list[Path]:
    return sorted(path for path in projects_dir.iterdir() if (path / ".git").exists())


def _disabled_l35_config() -> LocalInferenceConfig:
    return LocalInferenceConfig(
        base_url="http://127.0.0.1:9/v1",
        model="l35-disabled",
        timeout_seconds=0.05,
        provider_label="l35_disabled",
    )


def _quality_checks(interpretation: dict[str, Any]) -> dict[str, bool]:
    summary = str(interpretation.get("executive_summary") or "")
    capabilities = [str(item) for item in interpretation.get("capability_decomposition", [])]
    return {
        "external_l4_source": interpretation.get("source") == "external_l4",
        "has_summary": bool(summary.strip()),
        "summary_not_placeholder": summary.strip().lower() not in {"...", ".", "unknown", "n/a"},
        "project_anchored_summary": not _is_self_referential(summary),
        "capabilities_avoid_context_paths": not any(_mentions_context_path(item) for item in capabilities),
        "has_capabilities": bool(interpretation.get("capability_decomposition")),
        "has_refactor_plan": bool(interpretation.get("refactor_plan")),
        "has_cognitive_loop": bool(str(interpretation.get("cognitive_loop") or "").strip()),
        "has_open_questions": bool(interpretation.get("open_questions")),
        "no_fallback": not interpretation.get("fallback_reason"),
    }


def _is_self_referential(text: str) -> bool:
    lowered = text.lower()
    markers = ("level 4", "cognitive os", "deterministic facts", "level 3.5", "this prompt")
    return any(marker in lowered for marker in markers)


def _mentions_context_path(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("bench/", "benchmark", "test/", "tests/", "testing/", "test_", "testing.py", "integration/", "docs/", "ci/")
    )


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(cases)
    ok = sum(1 for case in cases if case["status"] == "ok")
    inference = [dict(case.get("inference") or {}) for case in cases]
    return {
        "ok": ok,
        "needs_review": count - ok,
        "l4_invoked": sum(1 for case in cases if case["l4_source"] == "external_l4"),
        "fallbacks": sum(1 for case in cases if case["fallback_reason"]),
        "avg_quality_score": round(sum(float(case["quality"]["quality_score"]) for case in cases) / count, 3) if count else 0.0,
        "quality_passed": sum(1 for case in cases if case["quality"]["passed"]),
        "quality_warnings": sum(len(case["quality"]["warnings"]) for case in cases),
        "model_output_clean": sum(1 for case in cases if case.get("model_output_clean")),
        "hardened_cases": sum(1 for case in cases if case.get("hardening_actions")),
        "hardening_actions": sum(len(case.get("hardening_actions", [])) for case in cases),
        "source_code_changes": sum(1 for case in cases if case["source_code_changes"] is True),
        "source_snapshot_unavailable": sum(1 for case in cases if not case.get("source_snapshot_available")),
        "high_confidence": sum(1 for case in cases if case["confidence"] == "high"),
        "medium_confidence": sum(1 for case in cases if case["confidence"] == "medium"),
        "low_confidence": sum(1 for case in cases if case["confidence"] == "low"),
        "inference_calls": sum(int(item.get("call_count") or 0) for item in inference),
        "latency_seconds": round(sum(float(item.get("latency_seconds") or 0.0) for item in inference), 3),
        "prompt_tokens": _sum_tokens(item.get("prompt_tokens") for item in inference),
        "completion_tokens": _sum_tokens(item.get("completion_tokens") for item in inference),
        "total_tokens": _sum_tokens(item.get("total_tokens") for item in inference),
    }


def _case_inference(records: list[dict[str, Any]]) -> dict[str, Any]:
    latency = round(sum(float(item.get("latency_seconds") or 0.0) for item in records), 3)
    total_tokens = _sum_tokens(item.get("total_tokens") for item in records)
    return {
        "call_count": len(records),
        "latency_seconds": latency,
        "prompt_tokens": _sum_tokens(item.get("prompt_tokens") for item in records),
        "completion_tokens": _sum_tokens(item.get("completion_tokens") for item in records),
        "total_tokens": total_tokens,
        "usage_reported": any(bool(item.get("usage_reported")) for item in records),
        "cached_response_suspected": bool(records) and latency < 0.1 and total_tokens is None,
    }


def _sum_tokens(values: Any) -> int | None:
    present = [int(value) for value in values if value is not None and int(value) > 0]
    return sum(present) if present else None


def _git_snapshot(project_dir: Path) -> str | None:
    resolved = project_dir.resolve()
    command_prefix = ["git", "-c", f"safe.directory={resolved.as_posix()}", "-C", str(resolved)]
    try:
        chunks = []
        for args in (
            ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
            ["diff", "--binary", "HEAD", "--"],
            ["diff", "--binary", "--cached", "HEAD", "--"],
        ):
            result = subprocess.run(command_prefix + args, check=False, capture_output=True, timeout=15)
            if result.returncode != 0:
                return None
            chunks.append(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return hashlib.sha256(b"\0".join(chunks)).hexdigest()


def _source_changed(before: str | None, after: str | None) -> bool | None:
    if before is None or after is None:
        return None
    return before != after


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['milestone']}",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Model: `{report['provider']['model']}`",
        f"Projects: `{report['project_count']}`",
        f"OK: `{report['summary']['ok']}`",
        f"Needs review: `{report['summary']['needs_review']}`",
        f"Average quality: `{report['summary']['avg_quality_score']}`",
        "",
        "## Cases",
    ]
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['project']}",
                f"- status: `{case['status']}`",
                f"- confidence: `{case['confidence']}`",
                f"- quality: `{case['quality']['quality_score']}`",
                f"- quality warnings: `{', '.join(case['quality']['warnings']) or 'none'}`",
                f"- hardening actions: `{', '.join(case['hardening_actions']) or 'none'}`",
                f"- inference: `{case['inference']}`",
                f"- summary: {case['executive_summary']}",
                f"- fallback: `{case['fallback_reason'] or 'none'}`",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
