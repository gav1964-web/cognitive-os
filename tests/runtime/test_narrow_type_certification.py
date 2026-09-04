from __future__ import annotations

import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.narrow_type_certification import build_narrow_type_certification


ROLES = ["project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer"]
STRATA = ["cli_local_tool", "library_pure_transform"]


def _receipt(root: Path, **check_overrides: bool) -> str:
    checks = {
        "independent_holdout": True,
        "lineage_disjoint": True,
        "no_role_regression": True,
        "role_chain_continuity": True,
        "generated_stub_gate": True,
        "inputs_digest_bound": True,
        **check_overrides,
    }
    source = root / "holdout.json"
    source.write_text(json.dumps({
        "artifact_type": "NarrowTypeHoldoutEvidence",
        "status": "passed",
        "checks": checks,
        "generated_stub_count": 0,
        "holdout_provenance": {"source_lineages": 3, "selection_digest": "sha256:" + "b" * 64},
    }), encoding="utf-8")
    entry = promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="holdout-runner:v1",
        evaluator_fingerprint="independent-evaluator:v1",
        replay_command=["python", "tools/narrow_holdout.py"],
    )
    return str(entry["ledger_path"])


def _evaluation(score: float = 9.8) -> dict:
    return {
        "cells": [
            {
                "role_id": role,
                "project_stratum": stratum,
                "score": score,
                "gaps": [],
                "promotion_eligible": True,
            }
            for stratum in STRATA
            for role in ROLES
        ]
    }


def test_narrow_types_require_scores_and_independent_receipt(tmp_path: Path):
    certification = build_narrow_type_certification(
        evaluation=_evaluation(),
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path),
    )

    assert certification["status"] == "certified"
    assert certification["promotion_eligible"] is True
    assert certification["promotion_applied"] is False
    assert certification["broad_strata"]["status"] == "deferred"


def test_narrow_type_certification_fails_one_weak_role(tmp_path: Path):
    evaluation = _evaluation()
    evaluation["cells"][0]["score"] = 9.69
    evaluation["cells"][0]["promotion_eligible"] = False

    certification = build_narrow_type_certification(
        evaluation=evaluation,
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path),
    )

    assert certification["status"] == "evidence_required"
    assert certification["promotion_eligible"] is False


def test_narrow_type_certification_rejects_role_regression(tmp_path: Path):
    certification = build_narrow_type_certification(
        evaluation=_evaluation(),
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path, no_role_regression=False),
    )

    assert certification["status"] == "evidence_required"
    assert certification["receipt_checks"]["no_role_regression"] is False


def test_narrow_type_certification_rejects_cell_evidence_gap(tmp_path: Path):
    evaluation = _evaluation()
    evaluation["cells"][0]["evidence_gaps"] = ["minimum_blind_cases"]

    certification = build_narrow_type_certification(
        evaluation=evaluation,
        evidence_root=tmp_path,
        holdout_receipt=_receipt(tmp_path),
    )

    assert certification["status"] == "evidence_required"
    assert certification["cell_checks"][0]["checks"]["evidence_complete"] is False
