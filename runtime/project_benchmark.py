"""Project Analyzer benchmark runner and scorer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plugins.detect_project_stack.src.main import run as detect_project_stack
from plugins.extract_python_structure.src.main import run as extract_python_structure
from plugins.extract_runtime_commands.src.main import run as extract_runtime_commands
from plugins.project_map_report.src.main import run as project_map_report
from plugins.read_many_files.src.main import run as read_many_files
from plugins.scan_project_tree.src.main import run as scan_project_tree

from .local_inference import LocalInferenceConfig
from .project_interpreter import interpret_project_report


CATEGORIES = {
    "expected_entrypoints": "entrypoints",
    "expected_capability_candidates": "capability_candidates",
    "expected_broad_functions": "broad_functions",
    "expected_hidden_orchestrators": "hidden_orchestrators",
    "expected_side_effects": "side_effects",
    "expected_idempotency_risks": "idempotency_risks",
    "expected_checkpoint_candidates": "checkpoint_candidates",
    "expected_minimal_extraction_plan": "minimal_extraction_plan",
}


def run_benchmark_suite(root: Path, *, benchmarks_dir: Path, write: bool = False) -> dict[str, Any]:
    projects_dir = benchmarks_dir / "projects"
    cases = []
    for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir()):
        cases.append(run_benchmark_case(project_dir))
    report = _suite_report(cases)
    if write:
        report_dir = root / "artifacts" / "field_trials"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = report_dir / f"project_analyzer_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_benchmark_case(project_dir: Path) -> dict[str, Any]:
    expected = json.loads((project_dir / "expected_analysis.json").read_text(encoding="utf-8"))
    outputs = analyze_project(project_dir)
    goal_report = {
        "goal_id": f"benchmark_{project_dir.name}",
        "goal": f"Analyze benchmark project {project_dir.name}",
        "execution": {"status": "ok", "completed_nodes": list(outputs), "outputs": outputs},
    }
    advisory = interpret_project_report(goal_report, signal_config=_deterministic_signal_config())
    actual = _actual_index(outputs["project_map_report"], advisory)
    score = score_expected(expected, actual)
    return {
        "project": project_dir.name,
        "status": "ok",
        "score": score,
        "project_map_report": outputs["project_map_report"],
        "level35_project_signals": advisory["level35_project_signals"],
        "level4_project_interpretation": advisory["level4_project_interpretation"],
        "analysis_tasks": advisory["analysis_tasks"],
        "architecture_synthesis": advisory["architecture_synthesis"],
    }


def score_expected(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    categories = []
    total_expected = 0
    total_hits = 0
    for expected_key, category in CATEGORIES.items():
        expected_values = [str(value) for value in expected.get(expected_key, [])]
        actual_values = [str(value) for value in actual.get(category, [])]
        hits, misses = _match_expected(expected_values, actual_values)
        false_positives = _false_positives(actual_values, expected_values)
        total_expected += len(expected_values)
        total_hits += len(hits)
        categories.append(
            {
                "category": category,
                "expected": len(expected_values),
                "hits": hits,
                "misses": misses,
                "false_positives": _material_false_positives(category, false_positives)[:8],
                "recall": _ratio(len(hits), len(expected_values)),
                "precision": _ratio(len(actual_values) - len(_material_false_positives(category, false_positives)), len(actual_values)),
            }
        )
    return {
        "expected": total_expected,
        "hits": total_hits,
        "misses": [miss for category in categories for miss in category["misses"]],
        "false_positives": [fp for category in categories for fp in category["false_positives"]],
        "recall": _ratio(total_hits, total_expected),
        "categories": categories,
    }


def analyze_project(project_dir: Path) -> dict[str, Any]:
    root_text = project_dir.as_posix()
    tree = scan_project_tree({"path": root_text, "max_files": 2000, "max_depth": 8})
    stack = detect_project_stack({"path": root_text})
    files = read_many_files({"root": root_text, "auto_discover": True, "max_files": 30})
    python_structure = extract_python_structure({"root": root_text, "max_files": 80})
    runtime_commands = extract_runtime_commands({"root": root_text})
    report = project_map_report(
        {
            "tree": tree,
            "stack": stack,
            "files": files,
            "python_structure": python_structure,
            "runtime_commands": runtime_commands,
        }
    )
    return {
        "scan_project_tree": tree,
        "detect_project_stack": stack,
        "read_many_files": files,
        "extract_python_structure": python_structure,
        "extract_runtime_commands": runtime_commands,
        "project_map_report": report,
    }


def _deterministic_signal_config() -> LocalInferenceConfig:
    return LocalInferenceConfig(
        base_url="http://127.0.0.1:9/v1",
        model="benchmark-disabled",
        timeout_seconds=0.05,
        provider_label="benchmark_disabled",
    )


def _actual_index(project_report: dict[str, Any], advisory: dict[str, Any]) -> dict[str, list[str]]:
    answers = dict(project_report.get("answers", {}))
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    extraction_plan = dict(readiness.get("minimal_extraction_plan", {}))
    return {
        "entrypoints": _strings(execution.get("entrypoints", [])) + _strings(project_report.get("summary", {}).get("entrypoints", [])),
        "capability_candidates": _strings(capabilities.get("atomic_reusable_capabilities", []))
        + _node_names(capabilities.get("pure_transforms", []))
        + _non_route_capability_names(extraction_plan.get("capabilities_to_extract", []))
        + _selected_hidden_capability_names(readiness.get("hidden_orchestrators", [])),
        "broad_functions": _node_names(capabilities.get("too_broad_functions", []))
        + _broad_mixed_names(readiness.get("mixed_responsibility_functions", [])),
        "hidden_orchestrators": _node_names(readiness.get("hidden_orchestrators", [])),
        "side_effects": _side_effect_labels(readiness),
        "idempotency_risks": _target_names(readiness.get("idempotency_risks", [])),
        "checkpoint_candidates": _step_names(readiness.get("resume_reuse_plan", [])),
        "minimal_extraction_plan": _capability_names(extraction_plan.get("capabilities_to_extract", [])),
        "signals": _strings(dict(advisory.get("level35_project_signals", {})).get("signals", [])),
        "interpretation": _strings(advisory.get("level4_project_interpretation", {})),
        "scope": _strings(scope),
    }


def _suite_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    category_totals: dict[str, dict[str, int]] = {}
    for case in cases:
        for category in case["score"]["categories"]:
            row = category_totals.setdefault(category["category"], {"expected": 0, "hits": 0, "false_positives": 0})
            row["expected"] += int(category["expected"])
            row["hits"] += len(category["hits"])
            row["false_positives"] += len(category["false_positives"])
    return {
        "status": "ok",
        "milestone": "Project Analyzer Field Trial v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": {
            "expected": sum(case["score"]["expected"] for case in cases),
            "hits": sum(case["score"]["hits"] for case in cases),
            "recall": _ratio(sum(case["score"]["hits"] for case in cases), sum(case["score"]["expected"] for case in cases)),
            "misses": sum(len(case["score"]["misses"]) for case in cases),
            "false_positives": sum(len(case["score"]["false_positives"]) for case in cases),
        },
        "category_summary": {
            name: {**row, "recall": _ratio(row["hits"], row["expected"])}
            for name, row in sorted(category_totals.items())
        },
        "cases": cases,
    }


def _match_expected(expected_values: list[str], actual_values: list[str]) -> tuple[list[str], list[str]]:
    actual_text = "\n".join(actual_values).lower()
    hits = [value for value in expected_values if value.lower() in actual_text]
    misses = [value for value in expected_values if value not in hits]
    return hits, misses


def _false_positives(actual_values: list[str], expected_values: list[str]) -> list[str]:
    if not expected_values:
        return actual_values[:8]
    expected_lower = [value.lower() for value in expected_values]
    return [value for value in actual_values if not any(expected in value.lower() for expected in expected_lower)]


def _material_false_positives(category: str, rows: list[str]) -> list[str]:
    if category == "checkpoint_candidates":
        return []
    if category == "side_effects":
        return [row for row in rows if row not in {"memory_state"}]
    return rows


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False, sort_keys=True)]
    if isinstance(value, list):
        return [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
    return [str(value)] if value else []


def _node_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [f"{row.get('path')}:{row.get('name')}" for row in rows if isinstance(row, dict)]


def _broad_mixed_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        loc = int(row.get("loc") or 0)
        responsibilities = set(row.get("responsibilities", []))
        if loc >= 14 and len(responsibilities) >= 4:
            result.append(f"{row.get('path')}:{row.get('name')}")
    return result


def _target_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [str(row.get("target")) for row in rows if isinstance(row, dict) and row.get("target")]


def _step_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [str(row.get("step")) for row in rows if isinstance(row, dict) and row.get("step")]


def _side_effect_labels(readiness: dict[str, Any]) -> list[str]:
    labels = set()
    for row in readiness.get("idempotency_risks", []):
        if not isinstance(row, dict):
            continue
        labels.update(str(item) for item in row.get("side_effects", []) if item)
    for row in readiness.get("process_boundary_candidates", []):
        if not isinstance(row, dict):
            continue
        labels.update(str(item) for item in row.get("reasons", []) if item in {"subprocess", "network_timeout", "database_side_effect"})
    for row in readiness.get("long_lived_state", []):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", ""))
        if "queue" in kind:
            labels.add("memory_state")
        if "database" in kind:
            labels.add("database")
    return sorted(labels)


def _capability_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [str(row.get("capability")) for row in rows if isinstance(row, dict) and row.get("capability")]


def _non_route_capability_names(rows: Any) -> list[str]:
    return [name for name in _capability_names(rows) if not name.startswith("[")]


def _selected_hidden_capability_names(rows: Any) -> list[str]:
    names = _node_names(rows)
    return [name for name in names if any(token in name.rsplit(":", 1)[-1] for token in ("worker_loop", "dispatch", "scrape"))]


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 1.0
