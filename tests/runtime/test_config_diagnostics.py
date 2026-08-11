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
    assert any(check["code"] == "foundation_semantic_quality_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "executable_acceptance_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "contract_transform_operators_integrity" for check in report["checks"])
    assert any(check["code"] == "contract_transform_contract_profiles_integrity" for check in report["checks"])
    assert any(check["code"] == "dependency_extraction_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "patch_synthesis_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "programmer_executor_playbooks_integrity" for check in report["checks"])
    assert any(check["code"] == "executor_solution_patterns_integrity" for check in report["checks"])
    assert any(check["code"] == "project_evolution_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "project_probe_env_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "pypi_archetype_kb_integrity" for check in report["checks"])
    assert any(check["code"] == "system_knowledge_ir_backlog_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "role_promotion_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "llm_profiles_integrity" for check in report["checks"])
    assert any(check["code"] == "role_source_policy_integrity" for check in report["checks"])


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


def test_config_mutation_sandbox_validates_executable_acceptance_policy(tmp_path: Path):
    target = ROOT / "config" / "executable_acceptance_policy.json"
    before = target.read_text(encoding="utf-8")
    proposal = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/executable_acceptance_policy.json",
        "operation": "replace_file",
        "content": json.loads(before),
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    report = validate_config_mutation(root=ROOT, proposal_path=proposal_path)

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
