import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.narrow_type_certification_reassessment import (
    build_narrow_type_certification_reassessment,
    verify_narrow_type_certification_reassessment,
)


def _receipt(root: Path, name: str, payload: dict) -> str:
    source = root / name
    source.write_text(json.dumps(payload), encoding="utf-8")
    return str(promote_evidence(
        root=root, source=source, producer_fingerprint=f"{name}:producer",
        evaluator_fingerprint=f"{name}:evaluator", replay_command=["python", name],
    )["ledger_path"])


def test_narrow_reassessment_revokes_nonsemantic_v1_certificate(tmp_path: Path) -> None:
    certificate = _receipt(tmp_path, "certificate.json", {
        "artifact_type": "NarrowTypeCertification",
        "schema_version": "narrow_type_certification.v1",
    })
    holdout = _receipt(tmp_path, "holdout.json", {
        "artifact_type": "NarrowTypeHoldoutEvidence",
        "schema_version": "narrow_type_holdout_evidence.v1",
        "checks": {"independent_holdout": True},
    })

    report = build_narrow_type_certification_reassessment(
        root=tmp_path, certificate_receipt=certificate, holdout_receipt=holdout
    )

    assert report["status"] == "revoked"
    assert report["affected_scope"]["downstream_mutation_evidence"] == "retained"
    assert verify_narrow_type_certification_reassessment(report) is True
