"""Summarize field-trial failure and skipped-executor patterns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("report", nargs="+")
    args = parser.parse_args()
    paths = [Path(item) for item in args.report]
    matrix = build_matrix(paths[0] if len(paths) == 1 else paths)
    output = summary_view(matrix) if args.summary_only else matrix
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if matrix["status"] == "ok" else 1


def summary_view(matrix: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in matrix.items() if key != "rows"}


def build_matrix(path: Path | list[Path]) -> dict[str, Any]:
    paths = path if isinstance(path, list) else [path]
    reports = [_load_report(item) for item in paths]
    if any(report.get("artifact_type") == "RoleFoundationFieldTrialReport" for _, report in reports):
        return _foundation_matrix(reports)
    report_path, report = reports[0]
    rows = [_case_row(case) for case in report.get("cases", [])]
    return {
        "artifact_type": "FieldTrialMatrix",
        "status": "ok",
        "report": report_path.as_posix(),
        "project_count": len(rows),
        "summary": {
            "status_counts": _counts(row["status"] for row in rows),
            "acceptance_signals": _counts(row["acceptance_signal"] for row in rows if row["acceptance_signal"]),
            "acceptance_skipped_reasons": _merge_counts(row["acceptance_skipped_reasons"] for row in rows),
            "acceptance_skipped_details": _counts(detail for row in rows for detail in row["acceptance_skipped_details"]),
            "patch_reasons": _counts(row["patch_reason"] for row in rows if row["patch_reason"]),
            "task_tree_statuses": _counts(row["task_tree_status"] for row in rows if row["task_tree_status"]),
            "task_tree_boundaries": _counts(row["task_tree_boundary"] for row in rows if row["task_tree_boundary"]),
            "strategy_actions": _counts(row["strategy_action"] for row in rows if row["strategy_action"]),
            "executor_playbooks": _counts(playbook for row in rows for playbook in row["executor_playbook_ids"]),
            "llm_strategy_statuses": _counts(row["llm_strategy_status"] for row in rows if row["llm_strategy_status"]),
            "sandbox_candidate_statuses": _counts(
                row["sandbox_candidate_status"] for row in rows if row["sandbox_candidate_status"]
            ),
            "sandbox_candidate_attempt_statuses": _counts(
                row["sandbox_candidate_attempt_status"] for row in rows if row["sandbox_candidate_attempt_status"]
            ),
            "sandbox_candidate_repair_statuses": _counts(
                row["sandbox_candidate_repair_status"] for row in rows if row["sandbox_candidate_repair_status"]
            ),
            "harness_counts": _counts(str(row["callable_harness_count"]) for row in rows),
            "failed_checks": _counts(code for row in rows for code in row["failed_checks"]),
        },
        "rows": rows,
    }


def _foundation_matrix(reports: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    reports = [
        (path, report)
        for path, report in reports
        if report.get("artifact_type") == "RoleFoundationFieldTrialReport"
    ]
    rows = [
        _foundation_case_row(path, case, target_score=float(report.get("target_score") or 9.5))
        for path, report in reports
        for case in report.get("cases", [])
    ]
    scored = [row for row in rows if row["status"] != "out_of_scope"]
    return {
        "artifact_type": "FoundationFieldTrialMatrix",
        "status": "ok",
        "reports": [path.as_posix() for path, _ in reports],
        "report_count": len(reports),
        "project_count": len(rows),
        "summary": {
            "status_counts": _counts(row["status"] for row in rows),
            "role_min_scores": _role_min_scores(scored),
            "readiness_min_score": _min_value(row["readiness_score"] for row in scored),
            "readiness_avg_score": _avg_value(row["readiness_score"] for row in scored),
            "below_target_count": sum(1 for row in scored if row["below_target"]),
            "out_of_scope_reasons": _counts(row["blocker"] for row in rows if row["status"] == "out_of_scope"),
            "selected_profile_ids": _counts(profile for row in scored for profile in row["semantic_profile_ids"]),
            "high_unprofiled_targets": _targets(
                row for row in scored if row["candidate_score"] >= 95 and not row["profiled_contract_family"]
            ),
            "contract_gap_targets": _targets(
                row for row in scored if row["candidate_score"] < 95 and not row["profiled_contract_family"]
            ),
            "weakest_targets": _weakest_targets(scored),
        },
        "rows": rows,
    }


def _foundation_case_row(report_path: Path, case: dict[str, Any], *, target_score: float) -> dict[str, Any]:
    quality = dict(case.get("selected_candidate_quality") or {})
    role_scores = dict(case.get("role_scores") or {})
    readiness = _case_readiness(case)
    return {
        "report": report_path.as_posix(),
        "project": case.get("project"),
        "status": case.get("status"),
        "pipeline_status": case.get("pipeline_status"),
        "blocker": case.get("blocker"),
        "project_min_score": float(case.get("project_min_score") or 0.0),
        "readiness_score": readiness,
        "below_target": readiness < target_score if case.get("status") != "out_of_scope" else False,
        "role_scores": role_scores,
        "selected_target": case.get("selected_extraction_candidate") or quality.get("target"),
        "candidate_score": int(quality.get("score") or 0),
        "candidate_status": quality.get("status"),
        "profiled_contract_family": bool(quality.get("profiled_contract_family")),
        "semantic_profile_ids": list(quality.get("semantic_profile_ids") or []),
        "warnings": list(case.get("warnings") or []),
    }


def _load_report(path: Path) -> tuple[Path, dict[str, Any]]:
    return path, json.loads(path.read_text(encoding="utf-8"))


def _case_readiness(case: dict[str, Any]) -> float:
    if case.get("status") == "ok":
        return round(float(case.get("project_min_score") or 0.0), 2)
    if case.get("status") == "blocked_ok":
        return 7.0
    if case.get("status") == "out_of_scope":
        return 0.0
    return round(min(5.0, float(case.get("project_min_score") or 0.0)), 2)


def _role_min_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        role: _min_value(dict(row.get("role_scores") or {}).get(role) for row in rows)
        for role in ("project_analyzer", "architect", "spec_writer")
    }


def _min_value(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(min(numbers), 2) if numbers else 0.0


def _avg_value(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 2) if numbers else 0.0


def _targets(rows: Any) -> list[dict[str, Any]]:
    return [
        {
            "project": row["project"],
            "target": row["selected_target"],
            "candidate_score": row["candidate_score"],
            "candidate_status": row["candidate_status"],
        }
        for row in rows
    ]


def _weakest_targets(rows: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (float(row["readiness_score"]), float(row["project_min_score"]), str(row["project"])))
    return [
        {
            "project": row["project"],
            "readiness_score": row["readiness_score"],
            "project_min_score": row["project_min_score"],
            "target": row["selected_target"],
            "candidate_score": row["candidate_score"],
            "profiled_contract_family": row["profiled_contract_family"],
            "semantic_profile_ids": row["semantic_profile_ids"],
        }
        for row in ordered[:limit]
    ]


def _case_row(case: dict[str, Any]) -> dict[str, Any]:
    executor = dict(case.get("executor") or {})
    target_chain = dict(case.get("target_chain") or {})
    return {
        "project": case.get("project"),
        "status": case.get("status"),
        "quality_score": case.get("quality_score"),
        "target": target_chain.get("implementation_target") or case.get("target"),
        "patch_status": executor.get("patch_synthesis_status") or case.get("patch_synthesis"),
        "patch_reason": executor.get("patch_synthesis_reason") or case.get("patch_reason"),
        "task_tree_status": executor.get("task_tree_status") or case.get("task_tree_status"),
        "task_tree_boundary": executor.get("task_tree_boundary") or case.get("task_tree_boundary"),
        "task_tree_node_count": executor.get("task_tree_node_count") or case.get("task_tree_node_count") or 0,
        "strategy_action": executor.get("strategy_action") or case.get("strategy_action"),
        "strategy_reason": executor.get("strategy_reason") or case.get("strategy_reason"),
        "executor_playbook_ids": list(executor.get("executor_playbook_ids") or case.get("executor_playbook_ids") or []),
        "llm_strategy_status": executor.get("llm_strategy_status") or case.get("llm_strategy_status"),
        "sandbox_candidate_status": executor.get("sandbox_candidate_status") or case.get("sandbox_candidate_status"),
        "sandbox_candidate_attempt_status": executor.get("sandbox_candidate_attempt_status")
        or case.get("sandbox_candidate_attempt_status"),
        "sandbox_candidate_attempt_reason": executor.get("sandbox_candidate_attempt_reason")
        or case.get("sandbox_candidate_attempt_reason"),
        "sandbox_candidate_repair_status": executor.get("sandbox_candidate_repair_status")
        or case.get("sandbox_candidate_repair_status"),
        "sandbox_candidate_repair_reason": executor.get("sandbox_candidate_repair_reason")
        or case.get("sandbox_candidate_repair_reason"),
        "acceptance_signal": executor.get("acceptance_signal") or case.get("acceptance_signal"),
        "acceptance_skipped_reasons": dict(executor.get("acceptance_skipped_reasons") or case.get("acceptance_skipped_reasons") or {}),
        "acceptance_skipped_details": _skipped_details(executor, case),
        "callable_harness_count": executor.get("callable_harness_count") or case.get("callable_harness_count") or 0,
        "failed_checks": [str(item.get("code")) for item in case.get("failed_checks", [])],
    }


def _skipped_details(executor: dict[str, Any], case: dict[str, Any]) -> list[str]:
    targets = executor.get("acceptance_skipped_targets") or case.get("acceptance_skipped_targets") or []
    return sorted(
        {
            str(item.get("detail"))
            for item in targets
            if isinstance(item, dict) and item.get("detail")
        }
    )


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _merge_counts(rows: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for key, value in dict(row).items():
            counts[str(key)] = counts.get(str(key), 0) + int(value)
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
