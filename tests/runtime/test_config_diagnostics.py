from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from runtime._parts.config_doctor_part2 import (
    _check_exception_pickle_reconstruction_knowledge,
    _check_project_development_boundary_knowledge,
    _check_project_development_policy,
    _check_project_native_cli_repair_knowledge,
)
from runtime.config_coverage import build_config_coverage_report
from runtime.config_doctor import run_config_doctor
from runtime.config_mutation_sandbox import validate_config_mutation
from runtime.patch_synthesis_policy import load_patch_synthesis_policy
from runtime.project_development import load_project_development_policy
from runtime.project_development_boundary_interpreter import (
    load_boundary_profiles,
    load_source_contrasts,
)


ROOT = Path(__file__).resolve().parents[2]


def test_config_doctor_passes_current_catalogs():
    report = run_config_doctor(ROOT)

    assert report["artifact_type"] == "ConfigDoctorReport"
    assert report["status"] == "ok"
    assert report["summary"]["failed"] == 0
    assert any(check["code"] == "operation_recipe_references" for check in report["checks"])
    assert any(check["code"] == "foundation_semantic_quality_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "role_project_type_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "pilot_blind_corpus_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "executable_acceptance_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "executable_acceptance_source_isolation_integrity" for check in report["checks"])
    assert any(check["code"] == "contract_transform_operators_integrity" for check in report["checks"])
    assert any(check["code"] == "contract_transform_contract_profiles_integrity" for check in report["checks"])
    assert any(check["code"] == "function_invocation_patterns_kb_integrity" for check in report["checks"])
    assert any(check["code"] == "dependency_extraction_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "patch_synthesis_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "programmer_executor_playbooks_integrity" for check in report["checks"])
    assert any(check["code"] == "programmer_task_tree_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "executor_solution_patterns_integrity" for check in report["checks"])
    assert any(check["code"] == "project_evolution_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "exception_pickle_reconstruction_knowledge_integrity" for check in report["checks"])
    assert any(check["code"] == "project_native_cli_repair_knowledge_integrity" for check in report["checks"])
    assert any(check["code"] == "project_probe_env_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "pypi_archetype_kb_integrity" for check in report["checks"])
    assert any(check["code"] == "system_knowledge_ir_backlog_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "role_promotion_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "llm_profiles_integrity" for check in report["checks"])
    assert any(check["code"] == "hypothesis_compiler_integrity" for check in report["checks"])
    assert any(check["code"] == "role_source_policy_integrity" for check in report["checks"])
    assert any(check["code"] == "source_line_limit_gate" for check in report["checks"])


def test_project_development_reducer_must_reference_patch_operation():
    policy = deepcopy(load_project_development_policy())
    policy["verified_issue_reducers"]["mixed_responsibility"] = ["extract_unverified_helper"]

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_unknown_reducer:"
        "mixed_responsibility.extract_unverified_helper"
    ) in check.errors


def test_cli_repair_knowledge_rejects_unknown_operator():
    catalog = json.loads(
        (ROOT / "knowledge" / "role_knowledge" / "project_native_cli_failure_repair_patterns.json").read_text(
            encoding="utf-8"
        )
    )
    catalog["patterns"][0]["operator_id"] = "unknown_cli_reducer"

    check = _check_project_native_cli_repair_knowledge({
        "project_native_cli_failure_repair_patterns": catalog,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_native_cli_repair_knowledge_unknown_operator:"
        "incomplete_import_token_contract"
    ) in check.errors


def test_exception_pickle_reconstruction_knowledge_rejects_source_apply():
    catalog = json.loads(
        (ROOT / "knowledge" / "role_knowledge" / "exception_pickle_reconstruction_patterns.json").read_text(
            encoding="utf-8"
        )
    )
    catalog["safety"]["source_apply_allowed"] = True

    check = _check_exception_pickle_reconstruction_knowledge({
        "exception_pickle_reconstruction_patterns": catalog,
    })

    assert "exception_pickle_reconstruction_knowledge_allows_source_apply" in check.errors


def test_project_development_feedback_policy_is_required():
    policy = deepcopy(load_project_development_policy())
    policy.pop("feedback_policy")

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert "project_development_policy_missing:feedback_policy.automatic_retry" in check.errors
    assert "project_development_policy_invalid:feedback_policy.preserve_allowed_targets" in check.errors


def test_project_development_feedback_hypothesis_kinds_are_closed():
    policy = deepcopy(load_project_development_policy())
    policy["feedback_policy"]["allowed_hypothesis_kinds"].append("unbounded_refactor")

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert "project_development_policy_invalid:feedback_policy.allowed_hypothesis_kinds" in check.errors


def test_project_development_replan_revision_remains_planning_only():
    policy = deepcopy(load_project_development_policy())
    policy["feedback_policy"]["replan_revision"]["executor_rerun_allowed"] = True

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_invalid:"
        "feedback_policy.replan_revision.executor_rerun_allowed"
    ) in check.errors


def test_project_development_bounded_experiment_cannot_authorize_execution():
    policy = deepcopy(load_project_development_policy())
    bounded = policy["feedback_policy"]["replan_revision"]["bounded_experiment"]
    bounded["execution_authorized"] = True
    bounded["allowed_actions"].append("invoke_executor")

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.execution_authorized"
    ) in check.errors
    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.allowed_actions"
    ) in check.errors


def test_project_development_bounded_research_cannot_enable_external_effects():
    policy = deepcopy(load_project_development_policy())
    bounded = policy["feedback_policy"]["replan_revision"]["bounded_experiment"]
    bounded["network_allowed"] = True
    bounded["subprocess_allowed"] = True

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.network_allowed"
    ) in check.errors
    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.subprocess_allowed"
    ) in check.errors


def test_project_development_source_contrast_identity_is_closed():
    policy = deepcopy(load_project_development_policy())
    profiles = deepcopy(load_boundary_profiles())
    contrasts = deepcopy(load_source_contrasts())
    contrast = next(
        row for row in contrasts["contrasts"]
        if row["contrast_id"] == "simple_loop_mapping_validated_o"
    )
    contrast["sha256"] = "short"

    check = _check_project_development_boundary_knowledge({
        "project_development_policy": policy,
        "project_development_boundary_profiles": profiles,
        "project_development_source_contrasts": contrasts,
    })

    assert (
        "project_development_boundary_knowledge_invalid_digest:"
        "simple_loop_mapping_validated_o"
    ) in check.errors


def test_project_development_human_approval_cannot_enable_execution():
    policy = deepcopy(load_project_development_policy())
    approval = policy["feedback_policy"]["replan_revision"]["bounded_experiment"][
        "human_approval"
    ]
    approval["execution_authorized"] = True
    approval["allowed_authorities"].append("model")

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.human_approval.execution_authorized"
    ) in check.errors
    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.human_approval.allowed_authorities"
    ) in check.errors


def test_project_development_design_gate_cannot_emit_executable_artifacts():
    policy = deepcopy(load_project_development_policy())
    design = policy["feedback_policy"]["replan_revision"]["bounded_experiment"][
        "human_approval"
    ]["implementation_design"]
    design["automatic_role_invocation"] = True
    design["forbidden_outputs"].remove("source_patch")

    check = _check_project_development_policy({
        "project_development_policy": policy,
        "patch_synthesis_policy": load_patch_synthesis_policy(),
    })

    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.human_approval.implementation_design.automatic_role_invocation"
    ) in check.errors
    assert (
        "project_development_policy_invalid:feedback_policy.replan_revision."
        "bounded_experiment.human_approval.implementation_design.forbidden_outputs"
    ) in check.errors


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


def test_config_mutation_sandbox_validates_object_merge(tmp_path: Path):
    proposal = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/executable_acceptance_policy.json",
        "operation": "merge_object",
        "path": "/structural_sample_policy",
        "content": {"maximum_inferred_length": 24},
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    report = validate_config_mutation(root=ROOT, proposal_path=proposal_path)

    assert report["status"] == "passed"
    assert report["target_modified"] is False
