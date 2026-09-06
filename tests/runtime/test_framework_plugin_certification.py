from __future__ import annotations

import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.framework_plugin_certification import (
    build_framework_plugin_certification,
    verify_framework_plugin_certification,
)
from runtime.framework_plugin_readiness import REQUIRED_ROLES


def _evaluation(*, promotion_eligible: bool = True) -> dict:
    return {"cells": [{
        "role_id": role,
        "project_stratum": "framework_plugin_build",
        "score": 9.8,
        "maturity": "mature",
        "evidence_gaps": [],
        "promotion_eligible": promotion_eligible,
    } for role in REQUIRED_ROLES]}


def _receipt(root: Path, *, no_role_regression: bool = True) -> str:
    source = root / "framework_holdout.json"
    source.write_text(json.dumps({
        "artifact_type": "FrameworkPluginHoldoutEvidence",
        "status": "passed",
        "checks": {
            "independent_holdout": True,
            "lineage_disjoint": True,
            "no_role_regression": no_role_regression,
            "role_chain_continuity": True,
            "generated_stub_gate": True,
            "inputs_digest_bound": True,
        },
        "generated_stub_count": 0,
        "holdout_provenance": {"source_lineages": 4},
    }), encoding="utf-8")
    entry = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="framework-holdout:v1",
        evaluator_fingerprint="independent-evaluator:v1",
        replay_command=["python", "tools/framework_plugin_holdout.py"],
    )
    return str(entry["ledger_path"])


def test_framework_certification_accepts_complete_durable_evidence(tmp_path: Path) -> None:
    report = build_framework_plugin_certification(
        evaluation=_evaluation(),
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path),
    )

    assert report["status"] == "certified"
    assert report["promotion_eligible"] is True
    assert verify_framework_plugin_certification(report) is True


def test_framework_certification_fails_closed_without_receipt(tmp_path: Path) -> None:
    report = build_framework_plugin_certification(
        evaluation=_evaluation(), evidence_root=tmp_path
    )

    assert report["status"] == "evidence_required"
    assert report["promotion_eligible"] is False
    assert report["receipt_status"] == "not_provided"


def test_framework_certification_rejects_regression(tmp_path: Path) -> None:
    report = build_framework_plugin_certification(
        evaluation=_evaluation(),
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path, no_role_regression=False),
    )

    assert report["status"] == "evidence_required"
    assert report["receipt_checks"]["no_role_regression"] is False


def test_framework_certification_requires_cell_promotion_eligibility(tmp_path: Path) -> None:
    report = build_framework_plugin_certification(
        evaluation=_evaluation(promotion_eligible=False),
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path),
    )

    assert report["status"] == "evidence_required"
    assert set(report["failed_cell_roles"]) == set(REQUIRED_ROLES)
