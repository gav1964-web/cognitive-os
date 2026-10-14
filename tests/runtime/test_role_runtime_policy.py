from __future__ import annotations

import pytest

from runtime.role_runtime_policy import RoleRuntimePolicyError, enforce_role_runtime_policy


def _directory() -> dict:
    return {
        "roles": {
            "bounded_role": {
                "policy": {"source_mutation": "forbidden"},
                "llm_policy": {"allowed": False},
                "kb_policy": {"auto_promote": False},
            }
        }
    }


@pytest.mark.parametrize(
    ("artifact", "reason"),
    [
        ({"llm_invoked": True}, "llm_invocation_forbidden"),
        ({"source_code_changes": True}, "source_mutation_forbidden"),
        ({"kb_auto_promoted": True}, "kb_auto_promotion_forbidden"),
    ],
)
def test_role_runtime_policy_blocks_forbidden_authority(artifact, reason):
    with pytest.raises(RoleRuntimePolicyError, match=reason):
        enforce_role_runtime_policy("bounded_role", artifact, directory=_directory())


def test_role_runtime_policy_allows_bounded_artifact():
    enforce_role_runtime_policy(
        "bounded_role",
        {"llm_invoked": False, "source_code_changes": False, "kb_auto_promoted": False},
        directory=_directory(),
    )
