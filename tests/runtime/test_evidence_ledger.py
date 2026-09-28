from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evidence_ledger import EvidenceLedgerError, promote_evidence, verify_evidence_entry


def _promote(root: Path) -> dict:
    source = root / "artifacts" / "trial.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"artifact_type": "TrialReport", "status": "passed"}), encoding="utf-8")
    return promote_evidence(
        root=root,
        source=source,
        producer_fingerprint="runner:v1",
        evaluator_fingerprint="reviewer:v2",
        replay_command=["python", "tools/trial.py", "--frozen"],
    )


def test_promoted_evidence_is_content_addressed_and_verifiable(tmp_path: Path):
    entry = _promote(tmp_path)

    result = verify_evidence_entry(root=tmp_path, ledger_path=Path(entry["ledger_path"]))

    assert result["status"] == "verified"
    assert result["evidence_payload"]["status"] == "passed"
    assert entry["content_sha256"].removeprefix("sha256:") in entry["artifact"]


def test_evidence_verification_detects_content_tampering(tmp_path: Path):
    entry = _promote(tmp_path)
    (tmp_path / entry["artifact"]).write_text("{}", encoding="utf-8")

    result = verify_evidence_entry(root=tmp_path, ledger_path=Path(entry["ledger_path"]))

    assert result["status"] == "invalid"
    assert "content_digest_mismatch" in result["errors"]


def test_promotion_requires_independent_evaluator(tmp_path: Path):
    source = tmp_path / "report.json"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(EvidenceLedgerError, match="independent"):
        promote_evidence(
            root=tmp_path,
            source=source,
            producer_fingerprint="same:v1",
            evaluator_fingerprint="same:v1",
            replay_command=["python", "trial.py"],
        )
