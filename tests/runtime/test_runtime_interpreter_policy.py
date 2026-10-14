from __future__ import annotations

from pathlib import Path

import pytest

from runtime.runtime_interpreter_policy import (
    RuntimeInterpreterPolicyError,
    code_change_requires_evidence,
    default_change_route,
    load_runtime_interpreter_policy,
)


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_interpreter_policy_is_configuration_first_for_l4_l45():
    policy = load_runtime_interpreter_policy(str(ROOT / "config" / "runtime_interpreter_policy.json"))

    assert {"L4", "L4.5"}.issubset(set(policy["configuration_first_layers"]))
    assert policy["target_distribution"]["configuration_or_registry_change_percent"] >= 90
    assert "executing raw LLM output" in policy["code_change_forbidden_for"]
    assert default_change_route("new_role", policy=policy) == "update_role_directory"
    assert default_change_route("new_input_output_combination", policy=policy) == "update_interface_contract_or_operation_recipe"
    assert "existing interpreter cannot express the task safely" in code_change_requires_evidence(policy=policy)


def test_runtime_interpreter_policy_rejects_low_configuration_first_target(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        """{
  "schema_version": "runtime_interpreter_policy.v1",
  "status": "active",
  "configuration_first_layers": ["L4", "L4.5"],
  "default_task_change_route": {},
  "code_change_allowed_only_for": [],
  "code_change_forbidden_for": ["executing raw LLM output"],
  "target_distribution": {"configuration_or_registry_change_percent": 50},
  "required_evidence_before_code_change": []
}
""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeInterpreterPolicyError, match="at least 90"):
        load_runtime_interpreter_policy(str(path))
