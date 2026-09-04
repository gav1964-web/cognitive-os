from __future__ import annotations

from collections import Counter
from typing import Any

from .patch_synthesis_policy import load_patch_synthesis_policy

CLUSTER_STRATEGIES = {
    "append_mapping_inside_effectful_loop": ("syntactic_extraction", True),
    "serialize_json_inside_filesystem_boundary": ("syntactic_extraction", True),
    "parse_text_inside_io_boundary": ("syntactic_extraction", True),
    "parse_json_inside_filesystem_boundary": ("syntactic_extraction", True),
    "parse_json_inside_network_boundary": ("semantic_boundary_research", False),
    "parse_structured_stream_inside_io_boundary": ("semantic_boundary_research", False),
    "dynamic_command_inside_subprocess_boundary": ("security_boundary_research", False),
    "request_mapping_inside_network_boundary": ("security_boundary_research", False),
    "network_response_parse_inside_effect_boundary": ("semantic_boundary_research", False),
    "response_mapping_inside_network_boundary": ("semantic_boundary_research", False),
}


def clusters(findings: list[dict[str, Any]], implemented_clusters: set[str]) -> list[dict[str, Any]]:
    totals = Counter(row["cluster"] for row in findings)
    unresolved = Counter(row["cluster"] for row in findings if not row["resolved_by_pure_helper"])
    rows = []
    for cluster, count in totals.most_common():
        unresolved_rows = [
            row for row in findings
            if row["cluster"] == cluster and not row["resolved_by_pure_helper"]
        ]
        strategy, automatic_recipe_eligible = CLUSTER_STRATEGIES.get(
            cluster, ("semantic_boundary_research", False)
        )
        rows.append(_cluster_row(
            cluster=cluster,
            count=count,
            unresolved_count=unresolved[cluster],
            unresolved_rows=unresolved_rows,
            implemented_clusters=implemented_clusters,
            strategy=strategy,
            automatic_recipe_eligible=automatic_recipe_eligible,
        ))
    return rows


def _cluster_row(
    *,
    cluster: str,
    count: int,
    unresolved_count: int,
    unresolved_rows: list[dict[str, Any]],
    implemented_clusters: set[str],
    strategy: str,
    automatic_recipe_eligible: bool,
) -> dict[str, Any]:
    samples = [row["source"] for row in unresolved_rows][:8]
    independent_projects = len({row["project"] for row in unresolved_rows})
    unique_shapes = len({row["structural_fingerprint"] for row in unresolved_rows})
    high_priority = independent_projects >= 2 and unique_shapes >= 2
    project_type_counts = {
        project_type: len({
            row["project"] for row in unresolved_rows
            if row["project_type"] == project_type
        })
        for project_type in sorted({row["project_type"] for row in unresolved_rows})
    }
    return {
        "cluster": cluster,
        "count": count,
        "unresolved_count": unresolved_count,
        "resolved_count": count - unresolved_count,
        "independent_project_count": independent_projects,
        "unique_structural_shape_count": unique_shapes,
        "recipe_priority": "high" if high_priority else "observe",
        "recipe_status": "implemented" if cluster in implemented_clusters else "missing",
        "recovery_strategy": strategy,
        "automatic_recipe_eligible": automatic_recipe_eligible,
        "project_type_counts": project_type_counts,
        "unresolved_samples": samples,
    }


def recommendation(cluster_rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        row for row in cluster_rows
        if row["recipe_priority"] == "high" and row["recipe_status"] != "implemented"
    ]
    selected = _select_cluster(eligible)
    return {
        "next_cluster": dict(selected or {}).get("cluster"),
        "reason": "highest repeated unresolved AST cluster" if selected else "no repeated unresolved cluster",
        "requires_source_review_before_recipe": selected is not None,
        "next_role": "researcher" if selected else None,
        "recovery_strategy": dict(selected or {}).get("recovery_strategy"),
        "automatic_recipe_eligible": dict(selected or {}).get("automatic_recipe_eligible"),
    }


def research_backlog(cluster_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for cluster in cluster_rows:
        if cluster["recipe_status"] == "implemented" or cluster["recipe_priority"] != "high":
            continue
        rows.append({
            "cluster": cluster["cluster"],
            "owner_role": "researcher",
            "handoff_role": "architect",
            "strategy": cluster["recovery_strategy"],
            "automatic_recipe_eligible": cluster["automatic_recipe_eligible"],
            "evidence": {
                "independent_project_count": cluster["independent_project_count"],
                "unique_structural_shape_count": cluster["unique_structural_shape_count"],
                "project_type_counts": cluster["project_type_counts"],
            },
            "research_question": research_question(cluster["cluster"]),
            "prohibited_shortcut": "do_not_label_effectful_stream_consumption_as_pure_helper",
        })
    return rows


def execution_lanes(cluster_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pending = [
        row for row in cluster_rows
        if row["recipe_priority"] == "high" and row["recipe_status"] != "implemented"
    ]
    research = _select_cluster([row for row in pending if not row["automatic_recipe_eligible"]])
    recipe = _select_cluster([row for row in pending if row["automatic_recipe_eligible"]])
    return {
        "research": {
            "cluster": dict(research or {}).get("cluster"),
            "role_chain": ["researcher", "architect"],
            "strategy": dict(research or {}).get("recovery_strategy"),
        },
        "recipe": {
            "cluster": dict(recipe or {}).get("cluster"),
            "role_chain": ["researcher", "architect", "developer", "tester", "architect"],
            "strategy": dict(recipe or {}).get("recovery_strategy"),
        },
    }


def _select_cluster(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(
        rows,
        key=lambda row: (
            row["independent_project_count"],
            row["unique_structural_shape_count"],
            row["unresolved_count"],
        ),
        default=None,
    )


def research_question(cluster: str) -> str:
    if cluster == "parse_structured_stream_inside_io_boundary":
        return "Can the stream be materialized at the adapter boundary without changing CSV dialect or newline behavior?"
    if cluster == "response_mapping_inside_network_boundary":
        return "Can response acquisition be separated from source-backed response projection?"
    if cluster == "network_response_parse_inside_effect_boundary":
        return "Can transport acquisition be separated from response decoding and schema validation?"
    if cluster == "request_mapping_inside_network_boundary":
        return "Which request fields belong to a pure request builder and which are transport policy?"
    return "Which explicit boundary contract preserves behavior while isolating effects?"


def implemented_clusters() -> set[str]:
    recipes = dict(load_patch_synthesis_policy().get("recipes") or {})
    return {
        str(recipe.get("target_cluster"))
        for recipe in recipes.values()
        if isinstance(recipe, dict)
        and recipe.get("enabled", True)
        and recipe.get("target_cluster")
    }
