"""Mine downloaded executor field reports for staged KB/playbook candidates."""

from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def mine_executor_corpus(report_paths: list[Path], *, max_candidates: int = 30) -> dict[str, Any]:
    cases = [case for path in report_paths for case in _load_cases(path)]
    candidates = [_candidate(case, skipped) for case in cases for skipped in list(case.get("acceptance_skipped_targets") or [])]
    candidates.extend(_case_candidate(case) for case in cases)
    candidates = [row for row in candidates if row]
    candidates.sort(key=lambda row: (row["priority"], row["project"], row["target"]))
    return {
        "artifact_type": "ExecutorCorpusMiningReport",
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_count": len(report_paths),
        "case_count": len(cases),
        "summary": {
            "candidate_count": len(candidates),
            "record_types": _counts(row["record_type"] for row in candidates),
            "reasons": _counts(row["reason"] for row in candidates),
            "priorities": _counts(row["priority"] for row in candidates),
        },
        "candidates": candidates[:max_candidates],
        "policy": {
            "automatic_kb_promotion_allowed": False,
            "automatic_source_mutation_allowed": False,
            "candidate_requires_regression_test": True,
            "candidate_requires_blind_delta": True,
        },
    }


def write_mining_report(report: dict[str, Any], *, root: Path, label: str = "executor_corpus_mining") -> Path:
    out_dir = root / "artifacts" / "knowledge_candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{label}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        return [dict(row) for row in list(payload.get("cases") or []) if isinstance(row, dict)]
    return []


def _candidate(case: dict[str, Any], skipped: dict[str, Any]) -> dict[str, Any] | None:
    reason = str(skipped.get("reason") or "")
    target = str(skipped.get("target") or "")
    project_dir = Path(str(case.get("project_dir") or ""))
    if not reason or not target:
        return None
    record_type, action, priority = _candidate_shape(reason, target)
    source_path = _target_path(project_dir, target)
    upstream_tests = _upstream_test_refs(project_dir, target)
    return {
        "record_type": record_type,
        "candidate_id": f"{record_type}:{_slug(target)}",
        "project": str(case.get("project") or ""),
        "target": target,
        "reason": reason,
        "detail": str(skipped.get("detail") or ""),
        "suggested_action": action,
        "priority": priority,
        "source_excerpt": _source_excerpt(source_path, target),
        "upstream_test_refs": upstream_tests,
        "evidence": {
            "acceptance_signal": case.get("acceptance_signal"),
            "boundary_track": case.get("boundary_track"),
            "playbook_ids": list(case.get("executor_playbook_ids") or []),
            "source_project_modified": bool(case.get("source_code_changes")),
            "upstream_tests_found": bool(upstream_tests),
        },
        "admission": {
            "auto_promote": False,
            "required_next_evidence": ["local_regression_test", "blind_trial_delta", "config_doctor_ok"],
        },
    }


def _case_candidate(case: dict[str, Any]) -> dict[str, Any] | None:
    level = str(case.get("patch_quality_level") or "")
    synthesis = str(case.get("patch_synthesis") or "")
    target = str(case.get("target") or "")
    if level not in {"verified_no_patch", "signature_fallback_guard", "blocked_handoff"}:
        return None
    record_type, action, priority = _case_candidate_shape(level, synthesis)
    project_dir = Path(str(case.get("project_dir") or ""))
    return {
        "record_type": record_type,
        "candidate_id": f"{record_type}:{_slug(str(case.get('project') or target or synthesis))}",
        "project": str(case.get("project") or ""),
        "target": target,
        "reason": str(case.get("patch_reason") or synthesis or level),
        "detail": f"patch_quality_level={level}; patch_synthesis={synthesis}",
        "suggested_action": action,
        "priority": priority,
        "source_excerpt": _source_excerpt(_target_path(project_dir, target), target) if target else "",
        "upstream_test_refs": _upstream_test_refs(project_dir, target) if target else [],
        "evidence": {
            "acceptance_signal": case.get("acceptance_signal"),
            "boundary_track": case.get("boundary_track"),
            "solution_pattern_ids": list(case.get("solution_pattern_ids") or []),
            "source_project_modified": bool(case.get("source_code_changes")),
        },
        "admission": {
            "auto_promote": False,
            "required_next_evidence": ["solution_pattern_review", "local_regression_test", "blind_trial_delta"],
        },
    }


def _case_candidate_shape(level: str, synthesis: str) -> tuple[str, str, str]:
    if level == "signature_fallback_guard":
        return "executor_solution_pattern_candidate", "add explicit negative contract before guard promotion", "high"
    if level == "blocked_handoff":
        return "executor_handoff_pattern_candidate", "improve target selection or boundary-specific handoff", "medium"
    if synthesis == "skipped":
        return "executor_verified_no_patch_candidate", "mine upstream tests before adding patch recipe", "medium"
    return "executor_review_candidate", "review manually before promotion", "low"


def _candidate_shape(reason: str, target: str) -> tuple[str, str, str]:
    if reason == "positive_sample_execution_failed":
        return "executor_fixture_profile_candidate", "derive controlled fixture from upstream tests", "high"
    if reason in {"import_failed_missing_module", "import_failed_import_error"}:
        return "executor_dependency_profile_candidate", "derive minimal dependency profile if external", "medium"
    if reason == "positive_signature_mismatch":
        return "executor_contract_rebind_candidate", "tighten SpecWriter or Implementer contract binding", "medium"
    if "search" in target.lower() or reason == "import_failed_runtime_error":
        return "executor_boundary_playbook_candidate", "record stateful/runtime boundary playbook", "medium"
    return "executor_review_candidate", "review manually before promotion", "low"


def _target_path(project_dir: Path, target: str) -> Path:
    path_text = target.split(":", 1)[0]
    return project_dir / path_text


def _upstream_test_refs(project_dir: Path, target: str, *, limit: int = 5) -> list[str]:
    symbol = target.rsplit(":", 1)[-1]
    if not project_dir.is_dir() or not symbol:
        return []
    refs: list[str] = []
    for path in project_dir.rglob("*.py"):
        rel = path.relative_to(project_dir).as_posix()
        if "/test" not in f"/{rel}" and "tests/" not in rel and "test_" not in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if symbol in text:
            refs.append(rel)
        if len(refs) >= limit:
            return refs
    return refs


def _source_excerpt(path: Path, target: str) -> str:
    symbol = target.rsplit(":", 1)[-1]
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text[:1200]
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            return "\n".join(lines[node.lineno - 1 : min(node.lineno + 40, len(lines))])[:1200]
    return text[:1200]


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")[:120]


def _counts(values: Any) -> dict[str, int]:
    counter = Counter(str(value) for value in values if value)
    return dict(sorted(counter.items()))
