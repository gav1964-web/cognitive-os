"""Cluster foundation field-trial gaps into KB growth candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.field_trial_matrix import build_matrix


RULES = [
    ("graphql_type_or_schema_boundary", ("graphql", "graphene", "strawberry", "schema", "fields_for_type")),
    ("jwt_or_jose_claim_serialization_boundary", ("jwt", "jose", "jwe", "claims", "serialize_json")),
    ("url_or_route_binding_boundary", ("url", "route", "bottle", "pyramid", "webargs", "add")),
    ("session_or_permission_auth_boundary", ("auth", "login", "principal", "permission", "session")),
    ("async_connection_transport_boundary", ("websocket", "engineio", "uvloop", "async_client", "connect")),
    ("native_extension_facade_boundary", ("native", "cffi", "rust", "greenlet", "msgspec", "zstandard")),
    ("type_annotation_structure_boundary", ("annotation", "typeddict", "annotations", "resolve_evaled_type")),
    ("parser_or_template_compilation_boundary", ("parse", "parser", "template", "dehumanize")),
    ("scheduler_or_rate_limit_state_boundary", ("acquire_jobs", "apscheduler", "limits", "memcached", "incr")),
    ("compiler_or_graph_ir_boundary", ("jaxpr", "cfg", "dead_branch", "pyright", "protocol", "enum")),
    ("report_formatter_boundary", ("report", "formatter", "bandit", "custom")),
    ("visualization_mapping_boundary", ("visualization", "matplotlib", "draw_edge_labels")),
    ("debug_or_trace_wrapper_boundary", ("debug", "trace", "wrap_trace")),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--output")
    parser.add_argument("report", nargs="+")
    args = parser.parse_args()
    result = build_gap_clusters([Path(item) for item in args.report], limit=args.limit)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "ok" else 1


def build_gap_clusters(paths: list[Path], *, limit: int = 12) -> dict[str, Any]:
    matrix = build_matrix(paths)
    rows = [
        row
        for row in matrix.get("rows", [])
        if row.get("status") != "out_of_scope" and not row.get("profiled_contract_family")
    ]
    groups = _group_rows(rows)
    clusters = sorted(groups.values(), key=_cluster_sort_key)[:limit]
    return {
        "artifact_type": "FoundationGapClusterReport",
        "status": "ok",
        "source_report_count": len(paths),
        "source_project_count": matrix.get("project_count", 0),
        "gap_project_count": len(rows),
        "summary": {
            "cluster_count": len(groups),
            "below_target_count": sum(1 for row in rows if row.get("below_target")),
            "high_unprofiled_count": sum(1 for row in rows if int(row.get("candidate_score") or 0) >= 95),
            "top_cluster_ids": [cluster["cluster_id"] for cluster in clusters[:5]],
        },
        "clusters": clusters,
    }


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        cluster_id = _infer_cluster_id(row)
        cluster = groups.setdefault(cluster_id, _empty_cluster(cluster_id))
        cluster["project_count"] += 1
        if row.get("below_target"):
            cluster["below_target_count"] += 1
        if int(row.get("candidate_score") or 0) >= 95:
            cluster["high_unprofiled_count"] += 1
        cluster["min_readiness_score"] = min(cluster["min_readiness_score"], float(row.get("readiness_score") or 0.0))
        cluster["avg_candidate_score_total"] += int(row.get("candidate_score") or 0)
        if len(cluster["examples"]) < 5:
            cluster["examples"].append(_example(row))
    for cluster in groups.values():
        count = max(1, int(cluster["project_count"]))
        cluster["avg_candidate_score"] = round(cluster.pop("avg_candidate_score_total") / count, 2)
        cluster["priority_score"] = _priority_score(cluster)
        cluster["proposed_profile_id"] = cluster["cluster_id"]
        cluster["growth_action"] = _growth_action(cluster)
    return groups


def _empty_cluster(cluster_id: str) -> dict[str, Any]:
    return {
        "cluster_id": cluster_id,
        "project_count": 0,
        "below_target_count": 0,
        "high_unprofiled_count": 0,
        "min_readiness_score": 10.0,
        "avg_candidate_score_total": 0,
        "examples": [],
    }


def _infer_cluster_id(row: dict[str, Any]) -> str:
    haystack = " ".join(
        str(value or "").lower()
        for value in (row.get("project"), row.get("selected_target"), row.get("candidate_status"))
    )
    for cluster_id, tokens in RULES:
        if any(token in haystack for token in tokens):
            return cluster_id
    target = str(row.get("selected_target") or "")
    stem = target.rsplit(":", 1)[-1].strip("_").lower()
    return f"{_compact_token(stem) or 'generic'}_contract_boundary"


def _compact_token(value: str) -> str:
    token = "".join(char if char.isalnum() else "_" for char in value)
    parts = [part for part in token.split("_") if part]
    return "_".join(parts[:4])


def _example(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": row.get("project"),
        "target": row.get("selected_target"),
        "candidate_score": row.get("candidate_score"),
        "readiness_score": row.get("readiness_score"),
    }


def _priority_score(cluster: dict[str, Any]) -> float:
    return round(
        cluster["below_target_count"] * 3.0
        + cluster["high_unprofiled_count"] * 2.0
        + cluster["project_count"] * 0.5
        + max(0.0, 9.5 - cluster["min_readiness_score"]),
        2,
    )


def _growth_action(cluster: dict[str, Any]) -> str:
    if cluster["below_target_count"] and cluster["high_unprofiled_count"]:
        return "add_profile_and_target_selection_rules"
    if cluster["below_target_count"]:
        return "add_contract_profile_with_acceptance_criteria"
    if cluster["high_unprofiled_count"]:
        return "promote_strong_unprofiled_shape_to_kb"
    return "watch_for_repetition"


def _cluster_sort_key(cluster: dict[str, Any]) -> tuple[float, int, str]:
    return (-float(cluster["priority_score"]), -int(cluster["project_count"]), str(cluster["cluster_id"]))


if __name__ == "__main__":
    raise SystemExit(main())
