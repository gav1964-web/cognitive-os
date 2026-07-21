from __future__ import annotations

import json
from pathlib import Path

from runtime.config_coverage import build_config_coverage_report
from runtime.config_doctor import run_config_doctor
from runtime.config_mutation_sandbox import validate_config_mutation


ROOT = Path(__file__).resolve().parents[2]


def test_config_doctor_passes_current_catalogs():
    report = run_config_doctor(ROOT)

    assert report["artifact_type"] == "ConfigDoctorReport"
    assert report["status"] == "ok"
    assert report["summary"]["failed"] == 0
    assert any(check["code"] == "operation_recipe_references" for check in report["checks"])


def test_config_coverage_reports_uncovered_entities_without_failing():
    report = build_config_coverage_report(ROOT)

    assert report["artifact_type"] == "ConfigCoverageReport"
    assert report["status"] == "ok"
    assert report["summary"]["entities"] >= report["summary"]["covered"]
    assert any(section["name"] == "l4_decision_rules" for section in report["sections"])


def test_config_mutation_sandbox_validates_without_modifying_target(tmp_path: Path):
    target = ROOT / "config" / "prompt_intake_rules.json"
    before = target.read_text(encoding="utf-8")
    proposal = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/prompt_intake_rules.json",
        "operation": "replace_file",
        "content": json.loads(before),
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    report = validate_config_mutation(root=ROOT, proposal_path=proposal_path)

    assert report["artifact_type"] == "ConfigMutationSandboxReport"
    assert report["status"] == "passed"
    assert report["target_modified"] is False
    assert target.read_text(encoding="utf-8") == before


def test_config_mutation_sandbox_blocks_invalid_config(tmp_path: Path):
    proposal = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/prompt_intake_rules.json",
        "operation": "replace_file",
        "content": {"schema_version": "bad"},
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    report = validate_config_mutation(root=ROOT, proposal_path=proposal_path)

    assert report["status"] == "blocked"
    assert report["validation"]["status"] == "failed"
