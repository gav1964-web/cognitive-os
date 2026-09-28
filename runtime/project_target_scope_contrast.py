"""Evaluate frozen, source-backed contrasts for target-scoped admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .project_recognition import recognize_project


def evaluate_target_scope_contrasts(*, root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = list(manifest.get("cases") or [])
    results = [_evaluate_case(root=root, case=dict(case)) for case in cases]
    positive_lineages = {
        str(result["lineage"])
        for result in results
        if result["expected_decision"] == "admitted" and result["matched"]
    }
    lineages = {str(result["lineage"]) for result in results}
    all_matched = bool(results) and all(result["matched"] for result in results)
    minimum_positive = int(manifest.get("minimum_independent_positive_lineages") or 2)
    return {
        "artifact_type": "ProjectTargetScopeContrastReport",
        "schema_version": "project_target_scope_contrast.v1",
        "status": "validated" if all_matched else "failed",
        "manifest": manifest_path.relative_to(root).as_posix(),
        "summary": {
            "case_count": len(results),
            "matched_count": sum(bool(result["matched"]) for result in results),
            "source_backed_lineage_count": len(lineages),
            "positive_lineage_count": len(positive_lineages),
            "boundary_validation": "passed" if all_matched else "failed",
            "independent_positive_transfer": (
                "passed" if len(positive_lineages) >= minimum_positive else "pending"
            ),
            "minimum_independent_positive_lineages": minimum_positive,
        },
        "capability_effect": "no_expansion",
        "results": results,
    }


def _evaluate_case(*, root: Path, case: dict[str, Any]) -> dict[str, Any]:
    project_dir = (root / str(case["project_dir"])).resolve()
    project_dir.relative_to(root.resolve())
    request = dict(case["change_request"])
    target_path = str(request["target"]).partition(":")[0]
    source = (project_dir / target_path).resolve()
    source.relative_to(project_dir)
    digest_before = _digest(source)

    # Expected labels remain outside the recognition input and are read only
    # after the matcher has produced its decision.
    decision = recognize_project(
        project=str(case["project"]),
        project_report={
            "answers": {
                "1_scope": {
                    "domain_profile": {"kind": str(case["classification"]["project_archetype"])}
                }
            }
        },
        classification=dict(case["classification"]),
        project_dir=project_dir,
        change_request=request,
    )
    route = dict(decision["pilot_route"])
    admission = dict(route.get("target_scope_admission") or {})
    observed_decision = "admitted" if admission.get("status") == "admitted" else "rejected"
    observed = {
        "pilot_status": route.get("status"),
        "decision": observed_decision,
        "reason": admission.get("reason"),
    }
    expected = dict(case["expected"])
    matched = all(observed.get(key) == value for key, value in expected.items())
    digest_after = _digest(source)
    return {
        "case_id": case["case_id"],
        "project": case["project"],
        "lineage": case["lineage"],
        "target": request["target"],
        "expected_decision": expected.get("decision"),
        "observed": observed,
        "matched": matched and digest_before == digest_after,
        "source_unchanged": digest_before == digest_after,
        "source_digest": digest_after,
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
