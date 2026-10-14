"""Researcher hypotheses and Architect gates for non-syntactic recovery boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOUNDARY_CONTRACTS = {
    "request_mapping_inside_network_boundary": {
        "pure_candidate": "build_request_payload",
        "effect_adapter": "transport_request",
        "preserve": ["authentication", "timeouts", "retry_policy", "request_encoding"],
        "question": "Which payload fields are domain data rather than transport policy?",
    },
    "network_response_parse_inside_effect_boundary": {
        "pure_candidate": "decode_response_payload",
        "effect_adapter": "transport_response",
        "preserve": ["status_handling", "error_mapping", "response_encoding", "missing_field_semantics"],
        "question": "What raw response contract can be decoded without owning transport behavior?",
    },
    "dynamic_command_inside_subprocess_boundary": {
        "pure_candidate": "build_command_arguments",
        "effect_adapter": "process_runner",
        "preserve": ["argument_order", "shell_mode", "environment", "exit_code_handling"],
        "question": "Can command construction be separated without weakening shell and path controls?",
    },
    "parse_structured_stream_inside_io_boundary": {
        "pure_candidate": "parse_materialized_records",
        "effect_adapter": "stream_reader",
        "preserve": ["newline_mode", "csv_dialect", "encoding", "iterator_error_timing"],
        "question": "Can the stream be materialized without changing parser behavior or error timing?",
    },
}


def build_recovery_boundary_research(
    audit_report: dict[str, Any],
    *,
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    clusters = [
        dict(row) for row in audit_report.get("clusters", [])
        if isinstance(row, dict)
        and row.get("recipe_priority") == "high"
        and row.get("recipe_status") != "implemented"
        and row.get("automatic_recipe_eligible") is False
    ]
    clusters.sort(
        key=lambda row: (
            int(row.get("independent_project_count") or 0),
            int(row.get("unique_structural_shape_count") or 0),
        ),
        reverse=True,
    )
    hypotheses = [_hypothesis(row) for row in clusters if row.get("cluster") in BOUNDARY_CONTRACTS]
    report = {
        "artifact_type": "RecoveryBoundaryResearch",
        "schema_version": "recovery_boundary_research.v1",
        "role": "researcher",
        "status": "architect_review_required" if hypotheses else "no_research_boundary",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "audit_report_path": audit_report.get("report_path"),
        "hypotheses": hypotheses,
        "architect_gate": {
            "status": "evidence_required" if hypotheses else "not_applicable",
            "automatic_admission": False,
            "developer_handoff_allowed": False,
            "required_before_handoff": [
                "source_review_confirms_data_direction",
                "boundary_contract_names_transport_invariants",
                "independent_holdout_matches_cluster",
                "differential_fixture_covers_success_and_failure",
            ] if hypotheses else [],
        },
        "safety": {
            "source_changes": False,
            "patch_synthesis": False,
            "network_execution": False,
            "subprocess_execution": False,
        },
    }
    if write:
        if root is None:
            raise ValueError("root is required when write=True")
        out = root / "artifacts" / "field_trials"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"recovery_boundary_research_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _hypothesis(cluster: dict[str, Any]) -> dict[str, Any]:
    cluster_id = str(cluster.get("cluster") or "")
    contract = dict(BOUNDARY_CONTRACTS[cluster_id])
    projects = int(cluster.get("independent_project_count") or 0)
    shapes = int(cluster.get("unique_structural_shape_count") or 0)
    return {
        "cluster": cluster_id,
        "status": "bounded_hypothesis",
        "confidence": round(min(0.9, 0.5 + 0.08 * min(projects, 3) + 0.03 * min(shapes, 5)), 2),
        "evidence": {
            "independent_project_count": projects,
            "unique_structural_shape_count": shapes,
            "samples": list(cluster.get("unresolved_samples") or []),
        },
        "boundary_contract": contract,
        "next_experiment": {
            "owner_role": "researcher",
            "review_role": "architect",
            "minimum_reviewed_projects": min(max(projects, 2), 3),
            "holdout_required": True,
            "failure_path_required": True,
        },
        "developer_request": None,
    }
