from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugins.project_map_report.src.language_scope import load_language_scope_policy
from runtime.architecture_decision_policy import load_architecture_decision_policy
from runtime.architecture_synthesis_policy import load_architecture_synthesis_policy
from runtime.config_doctor_self_improvement_catalogs import load_self_improvement_catalogs
from runtime.contract_transform_contract_profiles import load_contract_transform_contract_profiles
from runtime.contract_transform_operators import load_contract_transform_operators
from runtime.dependency_extraction_policy import load_dependency_extraction_policy
from runtime.executable_acceptance_policy import load_executable_acceptance_policy
from runtime.executor_solution_patterns import load_executor_solution_patterns
from runtime.foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from runtime.greenfield_architecture_patterns import load_greenfield_architecture_patterns
from runtime.interface_contracts import load_interface_contracts
from runtime.interpreter_authority import load_interpreter_authority_policy
from runtime.knowledge_import import load_pypi_archetype_rules
from runtime.l4_decision_table import load_l4_decision_rules
from runtime.local_inference import load_llm_profiles
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.patch_synthesis_policy import load_patch_synthesis_policy
from runtime.pilot_profile import load_pilot_profile
from runtime.programmer_executor_playbooks import load_programmer_executor_playbooks
from runtime.programmer_task_tree import load_programmer_task_tree_policy
from runtime.project_development import load_project_development_policy
from runtime.project_development_boundary_interpreter import (
    load_boundary_profiles,
    load_exception_pickle_patterns,
    load_source_contrasts,
)
from runtime.project_evolution_policy import load_project_evolution_policy
from runtime.project_probe_env_policy import load_project_probe_env_policy
from runtime.prompt_intake_rules import load_prompt_intake_rules
from runtime.role_directory import load_role_directory
from runtime.role_project_type_evaluation import load_role_project_type_policy
from runtime.role_promotion_policy import load_role_promotion_policy
from runtime.runtime_interpreter_policy import load_runtime_interpreter_policy
from runtime.sandbox_programmer_profiles import load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import load_sandbox_release_policy
from runtime.self_improvement_profile_families import load_contract_families
from runtime.self_development_l0_lifecycle import load_l0_lifecycle_policy
from runtime.corpus_evaluation_factory import load_corpus_evaluation_policy
from runtime.semantic_resolution_rules import load_semantic_resolution_rules
from runtime.semantic_target_profiles import load_semantic_target_profiles
from runtime.source_target_policy import load_role_source_policy
from runtime.stage2_template_routes import load_stage2_template_routes
from runtime.system_knowledge_ir_backlog import load_ir_backlog_policy
from runtime.target_quality_policy import load_target_quality_policy
from runtime.target_structural_families import load_structural_family_rules
from runtime.technical_spec_policy import load_technical_spec_policy
from runtime.web_extraction_profiles import load_web_extraction_profiles


def _load_catalogs(root: Path) -> dict[str, Any]:
    return {
        "role_directory": load_role_directory(str(root / "config" / "role_directory.json")),
        "runtime_interpreter_policy": load_runtime_interpreter_policy(str(root / "config" / "runtime_interpreter_policy.json")),
        "interpreter_authority_policy": load_interpreter_authority_policy(str(root / "config" / "interpreter_authority.json")),
        "corpus_evaluation_factory_policy": load_corpus_evaluation_policy(str(root / "config" / "corpus_evaluation_factory.json")),
        "self_development_l0_lifecycle": load_l0_lifecycle_policy(str(root / "config" / "self_development_l0_lifecycle.json")),
        "prompt_intake_rules": load_prompt_intake_rules(str(root / "config" / "prompt_intake_rules.json")),
        "semantic_resolution_rules": load_semantic_resolution_rules(str(root / "config" / "semantic_resolution_rules.json")),
        "semantic_target_profiles": load_semantic_target_profiles(str(root / "config" / "semantic_target_profiles.json")),
        "self_improvement_contract_families": load_contract_families(str(root / "config" / "self_improvement_contract_families.json")),
        **load_self_improvement_catalogs(root),
        "structural_contract_family_rules": load_structural_family_rules(str(root / "knowledge" / "contract_families" / "structural_recognition.json")),
        "stage2_template_routes": load_stage2_template_routes(str(root / "config" / "stage2_template_routes.json")),
        "web_extraction_profiles": load_web_extraction_profiles(str(root / "config" / "web_extraction_profiles.json")),
        "operation_recipe_rules": load_operation_recipe_rules(str(root / "config" / "operation_recipe_rules.json")),
        "sandbox_programmer_profiles": load_sandbox_programmer_profiles(str(root / "config" / "sandbox_programmer_profiles.json")),
        "sandbox_release_policy": load_sandbox_release_policy(str(root / "config" / "sandbox_release_policy.json")),
        "l4_decision_rules": load_l4_decision_rules(str(root / "config" / "l4_decision_rules.json")),
        "interface_contracts": load_interface_contracts(root),
        "greenfield_architecture_patterns": load_greenfield_architecture_patterns(str(root / "config" / "greenfield_architecture_patterns.json")),
        "target_quality_policy": load_target_quality_policy(str(root / "config" / "target_quality_policy.json")),
        "technical_spec_policy": load_technical_spec_policy(str(root / "config" / "technical_spec_policy.json")),
        "architecture_decision_policy": load_architecture_decision_policy(str(root / "config" / "architecture_decision_policy.json")),
        "architecture_synthesis_policy": load_architecture_synthesis_policy(str(root / "config" / "architecture_synthesis_policy.json")),
        "foundation_semantic_quality_policy": load_foundation_semantic_quality_policy(str(root / "config" / "foundation_semantic_quality_policy.json")),
        "role_project_type_policy": load_role_project_type_policy(root / "config" / "role_project_type_evaluation.json"),
        "pilot_profile": load_pilot_profile(root / "config" / "pilot_profile.json"),
        "pilot_blind_corpus_policy": _read_json(root / "config" / "pilot_blind_corpus_strata.json"),
        "executable_acceptance_policy": load_executable_acceptance_policy(str(root / "config" / "executable_acceptance_policy.json")),
        "contract_transform_operators": load_contract_transform_operators(str(root / "config" / "contract_transform_operators.json")),
        "contract_transform_contract_profiles": load_contract_transform_contract_profiles(str(root / "config" / "contract_transform_contract_profiles.json")),
        "dependency_extraction_policy": load_dependency_extraction_policy(str(root / "config" / "dependency_extraction_policy.json")),
        "patch_synthesis_policy": load_patch_synthesis_policy(str(root / "config" / "patch_synthesis_policy.json")),
        "programmer_executor_playbooks": load_programmer_executor_playbooks(str(root / "config" / "programmer_executor_playbooks.json")),
        "programmer_task_tree_policy": load_programmer_task_tree_policy(str(root / "knowledge" / "role_qa" / "programmer_task_tree_policy.json")),
        "executor_solution_patterns": load_executor_solution_patterns(str(root / "config" / "executor_solution_patterns.json")),
        "project_development_policy": load_project_development_policy(str(root / "config" / "project_development_policy.json")),
        "project_development_boundary_profiles": load_boundary_profiles(str(root / "knowledge" / "role_knowledge" / "project_development_boundary_profiles.json")),
        "project_development_source_contrasts": load_source_contrasts(str(root / "knowledge" / "role_knowledge" / "project_development_source_contrasts.json")),
        "exception_pickle_reconstruction_patterns": load_exception_pickle_patterns(str(root / "knowledge" / "role_knowledge" / "exception_pickle_reconstruction_patterns.json")),
        "project_native_cli_failure_repair_patterns": _read_json(root / "knowledge" / "role_knowledge" / "project_native_cli_failure_repair_patterns.json"),
        "project_evolution_policy": load_project_evolution_policy(str(root / "config" / "project_evolution_policy.json")),
        "project_probe_env_policy": load_project_probe_env_policy(str(root / "config" / "project_probe_env_policy.json")),
        "pypi_archetype_rules": load_pypi_archetype_rules(str(root / "knowledge" / "architecture_patterns" / "pypi_archetype_inference.json")),
        "ir_backlog_policy": load_ir_backlog_policy(str(root / "config" / "system_knowledge_ir_backlog_policy.json")),
        "role_promotion_policy": load_role_promotion_policy(str(root / "config" / "role_promotion_policy.json")),
        "llm_profiles": load_llm_profiles(str(root / "config" / "llm_profiles.json")),
        "role_source_policy": load_role_source_policy(str(root / "config" / "role_source_policy.json")),
        "sandbox_operations": _read_json(root / "registry" / "sandbox_programmer_operations.json"),
        "sandbox_compositions": _read_json(root / "registry" / "sandbox_programmer_compositions.json"),
        "sandbox_attempt_policy": _read_json(root / "registry" / "sandbox_attempt_policy.json"),
        "local_automation_cases": _read_json(root / "registry" / "local_automation_mvp_cases.json"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["_load_catalogs", "_read_json", "load_language_scope_policy"]
