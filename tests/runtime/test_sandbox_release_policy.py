from __future__ import annotations

from pathlib import Path

import pytest

from runtime.sandbox_release_policy import (
    SandboxReleasePolicyError,
    load_sandbox_release_policy,
    required_checks,
    sandbox_implementation_policy,
)


ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_release_policy_loads_required_checks_and_invariants():
    policy = load_sandbox_release_policy(str(ROOT / "config" / "sandbox_release_policy.json"))

    assert "raw_llm_not_executed" in required_checks("generated_package_evaluation", policy=policy)
    assert "llm_output_not_executed_directly" in required_checks("sandbox_programmer_admission", policy=policy)
    implementation = sandbox_implementation_policy(policy=policy)
    assert implementation["promotion_allowed"] is False
    assert implementation["llm_policy"]["llm_output_executed_directly"] is False


def test_sandbox_release_policy_rejects_raw_llm_execution(tmp_path: Path):
    path = tmp_path / "policy.json"
    path.write_text(
        """{
  "schema_version": "sandbox_release_policy.v1",
  "status": "active",
  "generated_package_evaluation": {"required_checks": ["prompt_present"]},
  "sandbox_programmer_admission": {"required_checks": ["sandbox_result_verified"]},
  "sandbox_implementation_result": {
    "promotion_allowed": false,
    "llm_policy": {"llm_output_executed_directly": true}
  }
}
""",
        encoding="utf-8",
    )

    with pytest.raises(SandboxReleasePolicyError, match="raw LLM"):
        load_sandbox_release_policy(str(path))
