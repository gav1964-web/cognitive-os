import json
from pathlib import Path

from runtime.evidence_ledger import promote_evidence
from runtime.framework_plugin_certification_reassessment import (
    build_framework_plugin_certification_reassessment,
    verify_framework_plugin_certification_reassessment,
)


def _prior_receipt(root: Path) -> str:
    source = root / "prior.json"
    source.write_text(json.dumps({
        "artifact_type": "FrameworkPluginCertification",
        "schema_version": "framework_plugin_certification.v1",
        "status": "certified",
        "certificate_digest": "sha256:old",
    }), encoding="utf-8")
    return str(promote_evidence(
        root=root, source=source, producer_fingerprint="old-cert:v1",
        evaluator_fingerprint="old-evaluator:v1", replay_command=["python", "old.py"],
    )["ledger_path"])


def test_reassessment_revokes_obsolete_semantically_invalid_certificate(tmp_path: Path) -> None:
    report = build_framework_plugin_certification_reassessment(
        root=tmp_path,
        prior_certificate_receipt=_prior_receipt(tmp_path),
        holdout_reassessment={
            "artifact_type": "FrameworkPluginHoldoutEvidence",
            "schema_version": "framework_plugin_holdout_evidence.v2",
            "checks": {
                "semantic_role_quality": False,
                "role_artifacts_auditable": True,
                "project_development_evaluated": False,
            },
        },
        role_regression={"status": "passed", "regression_count": 0},
    )

    assert report["status"] == "revoked"
    assert report["affected_scope"]["runtime_functionality"] == "not_revoked"
    assert verify_framework_plugin_certification_reassessment(report) is True
