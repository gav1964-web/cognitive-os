"""Summarize field-trial failure and skipped-executor patterns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    args = parser.parse_args()
    matrix = build_matrix(Path(args.report))
    print(json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if matrix["status"] == "ok" else 1


def build_matrix(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = [_case_row(case) for case in report.get("cases", [])]
    return {
        "artifact_type": "FieldTrialMatrix",
        "status": "ok",
        "report": path.as_posix(),
        "project_count": len(rows),
        "summary": {
            "status_counts": _counts(row["status"] for row in rows),
            "acceptance_signals": _counts(row["acceptance_signal"] for row in rows if row["acceptance_signal"]),
            "acceptance_skipped_reasons": _merge_counts(row["acceptance_skipped_reasons"] for row in rows),
            "acceptance_skipped_details": _counts(detail for row in rows for detail in row["acceptance_skipped_details"]),
            "patch_reasons": _counts(row["patch_reason"] for row in rows if row["patch_reason"]),
            "harness_counts": _counts(str(row["callable_harness_count"]) for row in rows),
            "failed_checks": _counts(code for row in rows for code in row["failed_checks"]),
        },
        "rows": rows,
    }


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
