from __future__ import annotations

from tools.github_reviewer_probe import _blocked_reason as reviewer_block_reason
from tools.github_reviewer_probe import _is_forbidden_source as reviewer_policy_forbidden
from tools.github_tester_probe import _blocked_reason as downstream_block_reason
from tools.github_tester_probe import _is_forbidden_source as downstream_policy_forbidden


def test_tester_and_reviewer_probes_share_context_only_source_policy():
    target = "integration_tests/python_modules/pkg/kind.py:create_cluster"

    assert downstream_policy_forbidden(target)
    assert reviewer_policy_forbidden(target)


def test_tester_and_reviewer_probes_detect_context_only_blocker():
    implementation_target = {"blocked_by": ["context_only_implementation_target"]}

    assert downstream_block_reason({}, implementation_target) == "context_only_implementation_target"
    assert reviewer_block_reason({}, implementation_target) == "context_only_implementation_target"


def test_context_only_sources_are_allowed_as_read_only_evidence_not_targets():
    target = "blocked_no_safe_candidate"
    evidence = "integration_tests/python_modules/pkg/kind.py:create_cluster"

    assert not downstream_policy_forbidden(target)
    assert not reviewer_policy_forbidden(target)
    assert downstream_policy_forbidden(evidence)
    assert reviewer_policy_forbidden(evidence)
