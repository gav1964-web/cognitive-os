"""Round-trip verifier for project rebuild trials."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_benchmark import analyze_project
from .project_rebuild_ir import build_project_rebuild_ir
from .system_knowledge_ir_backlog import build_ir_loss_backlog, summarize_ir_loss_backlog
from .system_knowledge_ir_diff import compare_system_knowledge_ir


def verify_rebuild_round_trip(*, source_ir: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    """Re-analyze generated project and compare its IR with the source IR."""

    try:
        target_outputs = analyze_project(target_dir)
        target_ir = build_project_rebuild_ir(source_dir=target_dir, analyzer_outputs=target_outputs)
        code_recovery_ir = build_project_rebuild_ir(
            source_dir=target_dir,
            analyzer_outputs=target_outputs,
            include_embedded=False,
        )
    except Exception as exc:  # pragma: no cover - defensive report path
        return {
            "artifact_type": "ProjectRebuildRoundTripReport",
            "status": "blocked",
            "reason": "target_project_analysis_failed",
            "error": str(exc),
            "target_project": target_dir.as_posix(),
        }
    diff = compare_system_knowledge_ir(source_ir, target_ir)
    code_recovery_diff = compare_system_knowledge_ir(source_ir, code_recovery_ir)
    backlog = build_ir_loss_backlog(diff)
    code_backlog = build_ir_loss_backlog(code_recovery_diff)
    return {
        "artifact_type": "ProjectRebuildRoundTripReport",
        "status": diff["status"],
        "code_recovery_status": code_recovery_diff["status"],
        "target_project": target_dir.as_posix(),
        "source_ir_schema": source_ir.get("schema_version"),
        "target_ir": _compact_target_ir(target_ir),
        "code_recovery_target_ir": _compact_target_ir(code_recovery_ir),
        "diff": diff,
        "code_recovery_diff": code_recovery_diff,
        "improvement_backlog": backlog,
        "backlog_summary": summarize_ir_loss_backlog(backlog),
        "code_recovery_backlog": code_backlog,
        "code_recovery_backlog_summary": summarize_ir_loss_backlog(code_backlog),
        "next_steps": _next_steps(diff),
    }


def _compact_target_ir(target_ir: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": target_ir.get("artifact_type"),
        "schema_version": target_ir.get("schema_version"),
        "origin": target_ir.get("origin"),
        "purpose": target_ir.get("purpose"),
        "project_identity": target_ir.get("project_identity"),
        "public_interfaces": list(target_ir.get("public_interfaces", []) or [])[:20],
        "behavior_contracts": list(target_ir.get("behavior_contracts", []) or [])[:20],
        "architecture_slices": list(target_ir.get("architecture_slices", []) or [])[:20],
        "acceptance_tests": list(target_ir.get("acceptance_tests", []) or [])[:20],
        "verification": target_ir.get("verification"),
    }


def _next_steps(diff: dict[str, Any]) -> list[str]:
    if diff.get("status") == "ok":
        return ["promote round-trip evidence into rebuild confidence report"]
    steps = ["turn IR losses into compiler backlog"]
    for loss in list(diff.get("losses", []) or [])[:4]:
        category = str(loss.get("category") or "unknown")
        steps.append(f"preserve {category} in generated project or generated docs")
    return steps
