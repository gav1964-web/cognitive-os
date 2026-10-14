"""Plan remaining exception-pickle import-isolation work by dependency cluster."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REPORT_DIR = Path("artifacts/project_development")


def run_exception_pickle_import_cluster_planner(
    *,
    root: Path,
    blocker_intelligence_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    intelligence = _read_json(root, blocker_intelligence_path or _latest_blocker_intelligence(root))
    clusters = _clusters(root, intelligence)
    return {
        "artifact_type": "ExceptionPickleImportClusterPlanner",
        "schema_version": "exception_pickle_import_cluster_planner.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if clusters else "empty",
        "blocker_intelligence": str(blocker_intelligence_path or _latest_blocker_intelligence(root)),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "recommended_next_cluster": clusters[0] if clusters else None,
        "source_apply": False,
        "kb_promotion": False,
    }


def _clusters(root: Path, intelligence: dict[str, Any]) -> list[dict[str, Any]]:
    probe_attempts = _latest_probe_attempts_by_target(root)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in intelligence.get("cases") or []:
        if not isinstance(case, dict):
            continue
        if case.get("next_operator_lane") != "import_dependency_isolation_candidate":
            continue
        profile = case.get("import_isolation_profile")
        if not isinstance(profile, dict):
            continue
        cluster = _cluster_id(profile)
        key = f"{case.get('project')}::{case.get('target')}"
        grouped[cluster].append({
            "case": case,
            "profile": profile,
            "latest_probe_attempt": probe_attempts.get(key),
        })
    rows = [_cluster_row(cluster, items) for cluster, items in grouped.items()]
    return sorted(rows, key=_cluster_sort_key)


def _cluster_id(profile: dict[str, Any]) -> str:
    missing = str(profile.get("missing_import") or "")
    kind = str(profile.get("missing_import_kind") or "unknown")
    if kind == "external_dependency" and missing:
        return f"external_dependency:{missing.split('.', 1)[0]}"
    if kind == "external_or_project_dependency" and missing:
        return f"external_or_project_dependency:{missing.split('.', 1)[0]}"
    if kind == "stdlib_symbol_compat" and missing:
        return f"stdlib_symbol_compat:{missing}"
    if kind == "stdlib_module_compat" and missing:
        return f"stdlib_module_compat:{missing}"
    subtype = str(profile.get("subtype") or "unknown")
    return f"{kind}:{subtype}"


def _cluster_row(cluster: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    projects = Counter(str(item["case"].get("project") or "") for item in items)
    blockers = Counter(str(item["profile"].get("blocker_kind") or "unknown") for item in items)
    subtypes = Counter(str(item["profile"].get("subtype") or "unknown") for item in items)
    risk_summary = Counter(_risk_bucket(item["profile"].get("target_replay_risk")) for item in items)
    direct_ready = [
        item
        for item in items
        if _is_direct_file_batch_candidate(item["profile"])
    ]
    failed_probe_attempts = [
        item
        for item in direct_ready
        if isinstance(item.get("latest_probe_attempt"), dict)
        and item["latest_probe_attempt"].get("status") != "applied_active_kb"
        and _probe_attempt_matches_cluster(
            item["latest_probe_attempt"],
            cluster=cluster,
            profile=item["profile"],
        )
    ]
    probe_blockers = Counter(
        str(item["latest_probe_attempt"].get("blocker_kind") or "unknown")
        for item in failed_probe_attempts
    )
    probe_reports = sorted({
        str(item["latest_probe_attempt"].get("_report_path") or "")
        for item in failed_probe_attempts
        if item["latest_probe_attempt"].get("_report_path")
    })
    return {
        "cluster": cluster,
        "case_count": len(items),
        "independent_project_count": len([project for project in projects if project]),
        "direct_file_batch_candidate_count": len(direct_ready),
        "failed_direct_file_probe_count": len(failed_probe_attempts),
        "failed_direct_file_probe_blocker_summary": dict(sorted(probe_blockers.items())),
        "latest_failed_probe_reports": probe_reports,
        "batch_readiness": _batch_readiness(
            items,
            len(direct_ready),
            failed_probe_count=len(failed_probe_attempts),
        ),
        "blocker_summary": dict(sorted(blockers.items())),
        "subtype_summary": dict(sorted(subtypes.items())),
        "target_replay_risk_summary": dict(sorted(risk_summary.items())),
        "representative_targets": [
            {
                "project": item["case"].get("project"),
                "target": item["case"].get("target"),
                "target_replay_risk": item["profile"].get("target_replay_risk"),
                "direct_file_preferred": item["profile"].get("direct_file_preferred"),
            }
            for item in items[:3]
        ],
        "next_action": _next_action(
            cluster,
            items,
            len(direct_ready),
            failed_probe_count=len(failed_probe_attempts),
        ),
    }


def _risk_bucket(value: Any) -> str:
    risk = int(value or 0)
    if risk <= 3:
        return "low"
    if risk <= 6:
        return "medium"
    return "high"


def _batch_readiness(
    items: list[dict[str, Any]],
    direct_ready_count: int,
    *,
    failed_probe_count: int = 0,
) -> str:
    if failed_probe_count:
        return "direct_file_probe_failed"
    if not direct_ready_count:
        return "not_batch_ready"
    if direct_ready_count == len(items):
        if _cluster_missing_import_kind(items) == "project_local_dependency":
            return "project_local_cluster_probe_required"
        return "cluster_batch_ready"
    if direct_ready_count and _cluster_missing_import_kind(items) == "project_local_dependency":
        return "partial_project_local_probe_required"
    return "partial_batch_probe_required"


def _next_action(
    cluster: str,
    items: list[dict[str, Any]],
    direct_ready_count: int,
    *,
    failed_probe_count: int = 0,
) -> str:
    if failed_probe_count:
        return "diagnose_failed_direct_file_probe"
    if direct_ready_count == len(items):
        if cluster.startswith("project_local_dependency:"):
            return "run_project_local_direct_file_probe"
        return "run_dependency_heavy_direct_file_batch"
    if direct_ready_count:
        if cluster.startswith("project_local_dependency:"):
            return "probe_project_local_direct_file_subset_before_write"
        return "probe_direct_file_subset_before_write"
    if cluster.startswith("stdlib_symbol_compat:"):
        return "case_level_stdlib_symbol_diagnosis"
    if cluster.startswith("external_or_project_dependency:"):
        return "separate_project_local_import_from_external_dependency"
    if any(str(item["profile"].get("subtype") or "") == "attribute_base_metaclass_risk" for item in items):
        return "class_state_contract_research_before_replay"
    return "hold_for_dependency_policy_or_new_replay_operator"


def _is_direct_file_batch_candidate(profile: dict[str, Any]) -> bool:
    missing_kind = str(profile.get("missing_import_kind") or "")
    subtype = str(profile.get("subtype") or "")
    if profile.get("direct_file_preferred") is not True:
        return False
    if int(profile.get("target_replay_risk") or 0) > 3:
        return False
    if subtype not in {"dependency_unavailable", "import_failed"}:
        return False
    if missing_kind == "external_dependency":
        return True
    if missing_kind != "project_local_dependency":
        return False
    return not (
        profile.get("has_attribute_base_class_definition") is True
        or profile.get("has_target_self_attribute_gap") is True
    )


def _cluster_missing_import_kind(items: list[dict[str, Any]]) -> str:
    kinds = {
        str(item["profile"].get("missing_import_kind") or "")
        for item in items
        if isinstance(item.get("profile"), dict)
    }
    return kinds.pop() if len(kinds) == 1 else "mixed"


def _probe_attempt_matches_cluster(
    attempt: dict[str, Any],
    *,
    cluster: str,
    profile: dict[str, Any],
) -> bool:
    missing_kind = str(profile.get("missing_import_kind") or "")
    report_profile = str(attempt.get("_report_import_isolation_batch_profile") or "")
    report_cluster = str(attempt.get("_report_import_isolation_cluster") or "")
    if missing_kind == "external_dependency":
        return report_profile == "dependency_heavy_direct_file" and report_cluster == cluster
    if missing_kind == "project_local_dependency":
        return report_profile == "project_local_direct_file" and report_cluster == cluster
    return report_cluster == cluster


def _cluster_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        int(row.get("failed_direct_file_probe_count") or 0),
        -int(row.get("direct_file_batch_candidate_count") or 0),
        -int(row.get("case_count") or 0),
        -int(row.get("independent_project_count") or 0),
        str(row.get("cluster") or ""),
    )


def _latest_probe_attempts_by_target(root: Path) -> dict[str, dict[str, Any]]:
    report_dir = root / DEFAULT_REPORT_DIR
    if not report_dir.is_dir():
        return {}
    attempts: dict[str, dict[str, Any]] = {}
    for path in sorted(report_dir.glob("exception_pickle_active_application_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(report, dict) or report.get("artifact_type") != "ExceptionPickleActiveApplicationTrial":
            continue
        if report.get("update_application_ledger") is not False:
            continue
        generated_at = str(report.get("generated_at") or path.name)
        for attempt in report.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            candidate = dict(attempt.get("candidate") or {})
            key = f"{candidate.get('project')}::{candidate.get('target')}"
            if key == "None::None":
                continue
            current = attempts.get(key)
            if current and str(current.get("_generated_at") or "") > generated_at:
                continue
            enriched = dict(attempt)
            enriched["_generated_at"] = generated_at
            enriched["_report_path"] = path.as_posix()
            enriched["_report_import_isolation_batch_profile"] = report.get(
                "import_isolation_batch_profile"
            )
            enriched["_report_import_isolation_cluster"] = report.get("import_isolation_cluster")
            attempts[key] = enriched
    return attempts


def _latest_blocker_intelligence(root: Path) -> Path:
    report_dir = root / DEFAULT_REPORT_DIR
    paths = sorted(report_dir.glob("exception_pickle_blocker_intelligence_*.json"))
    if not paths:
        raise FileNotFoundError("no exception-pickle blocker intelligence reports found")
    return paths[-1]


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    return json.loads(resolved.read_text(encoding="utf-8"))
