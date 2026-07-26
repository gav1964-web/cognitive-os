"""Benchmark greenfield Architect -> SpecWriter planning quality."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_artifact_quality import evaluate_greenfield_artifact_quality
from .greenfield_role_pipeline import run_greenfield_role_pipeline


def run_greenfield_prompt_benchmark(*, root: Path, benchmark_path: Path | None = None, write: bool = False) -> dict[str, Any]:
    source = benchmark_path or root / "benchmarks" / "greenfield_prompts" / "cases.json"
    corpus = _load_corpus(source)
    cases = [_run_case(root=root, case=dict(row), write=write) for row in corpus["cases"]]
    passed = sum(1 for row in cases if row["status"] == "passed")
    quality_scores = [float(row["quality"]["score"]) for row in cases]
    report = {
        "artifact_type": "GreenfieldPromptBenchmarkReport",
        "status": "ok" if passed == len(cases) else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": source.as_posix(),
        "summary": {
            "cases": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "avg_score": round(sum(float(row["score"]) for row in cases) / len(cases), 3) if cases else 0.0,
            "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0.0,
            "quality_needs_review": sum(1 for row in cases if row["quality"]["status"] != "ok"),
        },
        "cases": cases,
        "safety": {
            "implementation_started": False,
            "source_project_modified": False,
            "registry_changed": False,
            "llm_required": False,
        },
    }
    if write:
        out_dir = root / "artifacts" / "benchmarks" / "greenfield_prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"greenfield_prompt_benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _load_corpus(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "greenfield_prompt_benchmark.v1":
        raise ValueError("greenfield prompt benchmark must use schema_version greenfield_prompt_benchmark.v1")
    if payload.get("status") != "active":
        raise ValueError("greenfield prompt benchmark must be active")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("greenfield prompt benchmark requires non-empty cases")
    return payload


def _run_case(*, root: Path, case: dict[str, Any], write: bool) -> dict[str, Any]:
    report = run_greenfield_role_pipeline(
        root=root,
        prompt=str(case["prompt"]),
        question_mode=str(case.get("question_mode") or "continue_with_assumptions"),
        write=write,
        include_debug_artifacts=True,
    )
    quality = evaluate_greenfield_artifact_quality(
        architecture=_artifact(report, "product_architecture"),
        technical_spec=_artifact(report, "product_technical_spec") if report.get("artifacts", {}).get("product_technical_spec") else None,
    )
    checks = _score_case(case, report)
    score = sum(1 for row in checks if row["passed"]) / len(checks) if checks else 0.0
    passed = all(row["passed"] for row in checks) and quality["status"] == "ok"
    return {
        "id": str(case["id"]),
        "status": "passed" if passed else "failed",
        "score": round(score, 3),
        "quality": quality,
        "checks": checks,
        "actual": {
            "status": report.get("status"),
            "next_action": report.get("next_action"),
            "pattern_id": _summary_value(report, "product_architecture", "pattern_id"),
            "primary_contract": dict(report.get("primary_contract") or {}).get("name"),
            "component_ids": _component_ids(report),
            "spec_writer_started": dict(report.get("safety") or {}).get("spec_writer_started"),
            "clarification_prompt": report.get("clarification_prompt"),
        },
        "artifact_paths": {
            "product_architecture": _artifact_path(report, "product_architecture"),
            "product_technical_spec": _artifact_path(report, "product_technical_spec"),
            "report": report.get("report_path"),
        },
    }


def _score_case(case: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    actual_status = str(report.get("status"))
    expected_status = str(case.get("expected_status") or "ok")
    checks = [
        _check("status", actual_status == expected_status, expected_status, actual_status),
        _check("no_implementation", dict(report.get("safety") or {}).get("implementation_started") is False, False, dict(report.get("safety") or {}).get("implementation_started")),
        _check("no_source_or_registry_mutation", _no_mutation(report), True, _no_mutation(report)),
    ]
    pattern_id = _summary_value(report, "product_architecture", "pattern_id")
    checks.append(_check("pattern_id", pattern_id == case.get("expected_pattern_id"), case.get("expected_pattern_id"), pattern_id))
    expected_components = [str(item) for item in case.get("expected_components", [])]
    component_ids = _component_ids(report)
    for component in expected_components:
        checks.append(_check(f"component:{component}", component in component_ids, component, component_ids))
    expected_contract = case.get("expected_primary_contract")
    if expected_contract:
        actual_contract = dict(report.get("primary_contract") or {}).get("name")
        checks.append(_check("primary_contract", actual_contract == expected_contract, expected_contract, actual_contract))
    architecture_blob = json.dumps(_artifact(report, "product_architecture"), ensure_ascii=False).lower()
    spec_blob = json.dumps(_artifact(report, "product_technical_spec"), ensure_ascii=False).lower()
    combined_blob = f"{architecture_blob}\n{spec_blob}"
    for marker in [str(item) for item in case.get("expected_research_markers", [])]:
        checks.append(_check(f"research_marker:{marker}", marker.lower() in combined_blob, marker, combined_blob[:360]))
    if expected_status == "needs_clarification":
        prompt = str(report.get("clarification_prompt") or "")
        checks.append(_check("spec_writer_not_started", dict(report.get("safety") or {}).get("spec_writer_started") is False, False, dict(report.get("safety") or {}).get("spec_writer_started")))
        for marker in [str(item) for item in case.get("expected_clarification_markers", [])]:
            checks.append(_check(f"clarification_marker:{marker}", marker in prompt, marker, prompt[:240]))
    else:
        checks.append(_check("spec_writer_started", dict(report.get("safety") or {}).get("spec_writer_started") is True, True, dict(report.get("safety") or {}).get("spec_writer_started")))
        checks.append(_check("technical_spec_present", _artifact(report, "product_technical_spec").get("artifact_type") == "ProductTechnicalSpec", "ProductTechnicalSpec", _artifact(report, "product_technical_spec").get("artifact_type")))
    return checks


def _check(name: str, passed: bool, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "expected": expected, "actual": actual}


def _artifact(report: dict[str, Any], name: str) -> dict[str, Any]:
    artifact = dict(dict(report.get("_debug_artifacts") or {}).get(name) or {})
    if artifact:
        return artifact
    summary = dict(dict(report.get("artifacts") or {}).get(name) or {})
    path = summary.get("path")
    if path:
        try:
            return json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except OSError:
            return summary
    return summary


def _artifact_value(report: dict[str, Any], name: str, field: str) -> Any:
    return _artifact(report, name).get(field)


def _summary_value(report: dict[str, Any], name: str, field: str) -> Any:
    return dict(dict(report.get("artifacts") or {}).get(name) or {}).get(field)


def _artifact_path(report: dict[str, Any], name: str) -> str | None:
    summary = dict(dict(report.get("artifacts") or {}).get(name) or {})
    path = summary.get("path")
    return str(path) if path else None


def _component_ids(report: dict[str, Any]) -> list[str]:
    summary_ids = dict(dict(report.get("artifacts") or {}).get("product_architecture") or {}).get("component_ids")
    if isinstance(summary_ids, list):
        return [str(item) for item in summary_ids]
    return [str(row.get("id")) for row in _artifact(report, "product_architecture").get("components", []) if isinstance(row, dict)]


def _no_mutation(report: dict[str, Any]) -> bool:
    safety = dict(report.get("safety") or {})
    return (
        safety.get("source_project_modified") is False
        and safety.get("registry_changed") is False
        and safety.get("implementation_started") is False
    )
