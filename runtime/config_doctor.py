"""Cross-check external runtime configuration catalogs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .interface_contracts import load_interface_contracts
from .l4_decision_table import load_l4_decision_rules
from .operation_recipe_rules import load_operation_recipe_rules
from .prompt_intake_rules import load_prompt_intake_rules
from .role_directory import load_role_directory
from .runtime_interpreter_policy import load_runtime_interpreter_policy
from .sandbox_programmer_profiles import load_sandbox_programmer_profiles
from .sandbox_release_policy import load_sandbox_release_policy
from .semantic_resolution_rules import load_semantic_resolution_rules
from .stage2_template_routes import load_stage2_template_routes


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class _Check:
    code: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": "failed" if self.errors else "passed",
            "errors": self.errors,
            "warnings": self.warnings,
        }


def run_config_doctor(root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT).resolve()
    checks = [
        _load_check(
            "load_external_config_catalogs",
            lambda: _load_catalogs(base),
        ),
    ]
    catalogs = _load_catalogs(base)
    checks.extend(
        [
            _check_role_directory(catalogs),
            _check_stage2_routes(catalogs, base),
            _check_semantic_resolution(catalogs),
            _check_operation_recipes(catalogs),
            _check_sandbox_programmer(catalogs),
            _check_sandbox_attempt_policy(catalogs, base),
            _check_l4_decision_rules(catalogs),
        ]
    )
    rows = [check.to_dict() for check in checks]
    failed = [row for row in rows if row["status"] == "failed"]
    return {
        "artifact_type": "ConfigDoctorReport",
        "status": "failed" if failed else "ok",
        "root": base.as_posix(),
        "summary": {
            "passed": len(rows) - len(failed),
            "failed": len(failed),
            "warnings": sum(len(row["warnings"]) for row in rows),
        },
        "checks": rows,
    }


def _load_check(code: str, fn: Callable[[], Any]) -> _Check:
    check = _Check(code)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - doctor reports config failures.
        check.errors.append(f"{type(exc).__name__}:{exc}")
    return check


def _load_catalogs(root: Path) -> dict[str, Any]:
    return {
        "role_directory": load_role_directory(str(root / "config" / "role_directory.json")),
        "runtime_interpreter_policy": load_runtime_interpreter_policy(str(root / "config" / "runtime_interpreter_policy.json")),
        "prompt_intake_rules": load_prompt_intake_rules(str(root / "config" / "prompt_intake_rules.json")),
        "semantic_resolution_rules": load_semantic_resolution_rules(str(root / "config" / "semantic_resolution_rules.json")),
        "stage2_template_routes": load_stage2_template_routes(str(root / "config" / "stage2_template_routes.json")),
        "operation_recipe_rules": load_operation_recipe_rules(str(root / "config" / "operation_recipe_rules.json")),
        "sandbox_programmer_profiles": load_sandbox_programmer_profiles(str(root / "config" / "sandbox_programmer_profiles.json")),
        "sandbox_release_policy": load_sandbox_release_policy(str(root / "config" / "sandbox_release_policy.json")),
        "l4_decision_rules": load_l4_decision_rules(str(root / "config" / "l4_decision_rules.json")),
        "interface_contracts": load_interface_contracts(root),
        "sandbox_operations": _read_json(root / "registry" / "sandbox_programmer_operations.json"),
        "sandbox_compositions": _read_json(root / "registry" / "sandbox_programmer_compositions.json"),
        "sandbox_attempt_policy": _read_json(root / "registry" / "sandbox_attempt_policy.json"),
        "local_automation_cases": _read_json(root / "registry" / "local_automation_mvp_cases.json"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_role_directory(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_directory_pipeline_integrity")
    directory = catalogs["role_directory"]
    roles = dict(directory.get("roles") or {})
    outputs: set[str] = set()
    for step in directory.get("pipeline", []):
        role_id = str(dict(step).get("role_id") or "")
        role = dict(roles.get(role_id) or {})
        if role_id not in roles:
            check.errors.append(f"unknown_pipeline_role:{role_id}")
            continue
        output_key = str(dict(step).get("output_key") or "")
        if output_key in outputs:
            check.errors.append(f"duplicate_pipeline_output_key:{output_key}")
        outputs.add(output_key)
        builder = dict(role.get("artifact_builder") or {})
        if not builder.get("callable") or not builder.get("artifact_type"):
            check.errors.append(f"missing_builder_contract:{role_id}")
    return check


def _check_stage2_routes(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("stage2_template_routes_integrity")
    routes = catalogs["stage2_template_routes"]
    known = {str(item) for item in routes.get("known_templates", [])}
    routed = {str(dict(row).get("case") or "") for row in routes.get("routes", [])}
    for case_name in sorted(routed - known):
        check.errors.append(f"route_unknown_case:{case_name}")
    for case_name in sorted(known - routed):
        check.warnings.append(f"known_template_without_route:{case_name}")
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for case_name in sorted(known):
        if not (curriculum / case_name / "teacher_reference.json").is_file():
            check.warnings.append(f"template_without_teacher_reference:{case_name}")
    return check


def _check_semantic_resolution(catalogs: dict[str, Any]) -> _Check:
    check = _Check("semantic_resolution_references")
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    rules = catalogs["semantic_resolution_rules"]
    for row in rules.get("existing_resolution_rules", []):
        required = str(dict(row).get("required_template") or "")
        if required not in known:
            check.errors.append(f"semantic_rule_unknown_template:{required}")
    return check


def _check_operation_recipes(catalogs: dict[str, Any]) -> _Check:
    check = _Check("operation_recipe_references")
    rules = catalogs["operation_recipe_rules"]
    contracts = set(catalogs["interface_contracts"])
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    for contract in rules.get("allowed_interface_contracts", []):
        if str(contract) not in contracts:
            check.errors.append(f"unknown_interface_contract:{contract}")
    for contract, profile in dict(rules.get("contract_profiles") or {}).items():
        if str(contract) not in contracts:
            check.errors.append(f"contract_profile_unknown_contract:{contract}")
        if str(profile) not in profiles:
            check.errors.append(f"contract_profile_unknown_profile:{profile}")
    for row in rules.get("text_interface_resolution", []):
        contract = str(dict(row).get("interface_contract") or "")
        if contract not in contracts:
            check.errors.append(f"text_resolution_unknown_contract:{contract}")
    return check


def _check_sandbox_programmer(catalogs: dict[str, Any]) -> _Check:
    check = _Check("sandbox_programmer_registry_integrity")
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    operations = {str(row.get("id") or ""): dict(row) for row in catalogs["sandbox_operations"].get("operations", [])}
    for operation_id, row in sorted(operations.items()):
        profile = str(row.get("profile") or "")
        if profile not in profiles:
            check.errors.append(f"operation_unknown_profile:{operation_id}:{profile}")
    seen = set()
    for operation_id in operations:
        if operation_id in seen:
            check.errors.append(f"duplicate_operation_id:{operation_id}")
        seen.add(operation_id)
    for composition in catalogs["sandbox_compositions"].get("compositions", []):
        for step in dict(composition).get("steps", []):
            operation_id = str(dict(step).get("operation") or "")
            if operation_id not in operations:
                check.errors.append(f"composition_unknown_operation:{dict(composition).get('id')}:{operation_id}")
    return check


def _check_sandbox_attempt_policy(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("sandbox_attempt_policy_references")
    policy = catalogs["sandbox_attempt_policy"]
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for kind, entry in dict(policy.get("allowed_attempt_kinds") or {}).items():
        for case_name in dict(entry).get("cases", []):
            case = str(case_name)
            if case not in known:
                check.errors.append(f"attempt_kind_unknown_case:{kind}:{case}")
            if dict(entry).get("requires_curriculum_reference") and not (curriculum / case / "teacher_reference.json").is_file():
                check.errors.append(f"attempt_kind_missing_teacher_reference:{kind}:{case}")
    return check


def _check_l4_decision_rules(catalogs: dict[str, Any]) -> _Check:
    check = _Check("l4_decision_rule_integrity")
    seen = set()
    for rule in catalogs["l4_decision_rules"].get("rules", []):
        rule_id = str(dict(rule).get("rule_id") or "")
        if rule_id in seen:
            check.errors.append(f"duplicate_l4_rule_id:{rule_id}")
        seen.add(rule_id)
        if not dict(rule).get("next_action"):
            check.errors.append(f"l4_rule_without_next_action:{rule_id}")
    return check
