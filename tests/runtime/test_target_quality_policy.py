from __future__ import annotations

from runtime.role_spec_writer_ranking import name_and_contract_score
from runtime.target_quality import semantic_target_quality_report
from runtime.target_quality_policy import load_target_quality_policy


def test_target_quality_policy_loads_required_sections():
    policy = load_target_quality_policy()

    assert policy["schema_version"] == "target_quality_policy.v1"
    assert "target_quality" in policy
    assert "spec_writer_ranking" in policy
    assert policy["target_quality"]["suspicious_path_tokens"]
    assert policy["spec_writer_ranking"]["deterministic_shape_tokens"]


def test_target_quality_policy_drives_quality_and_ranking_rules():
    weak = semantic_target_quality_report(
        "pkg/utils/helper.py:version",
        ranked_candidates=["pkg/utils/helper.py:version"],
        source_evidence=["pkg/utils/helper.py:version"],
    )
    strong = semantic_target_quality_report(
        "pkg/parser.py:parse_payload",
        ranked_candidates=["pkg/parser.py:parse_payload"],
        source_evidence=["pkg/parser.py:parse_payload"],
    )
    score, reasons = name_and_contract_score(
        "pkg/parser.py:parse_payload",
        {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
        [],
    )

    assert weak["status"] in {"suspicious", "poor"}
    assert strong["status"] == "strong"
    assert score > 0
    assert "deterministic parser" in " ".join(reasons)


def test_validate_url_contract_is_not_treated_as_trivial_url_accessor():
    target = "package/utils.py:_validate_repository_url"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="deterministic parser/normalizer/validator shape",
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert not any("trivial accessor" in reason for reason in report["reasons"])


def test_profiled_version_operation_is_not_treated_as_support_version_helper():
    report = semantic_target_quality_report(
        "django_redis/client/default.py:incr_version",
        ranked_candidates=["django_redis/client/default.py:incr_version"],
        source_evidence=["django_redis/client/default.py:incr_version"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert not any("support/utility target: version" in reason for reason in report["reasons"])


def test_command_entrypoint_profile_reaches_excellent_score():
    report = semantic_target_quality_report(
        "src/trustme/_cli.py:main",
        ranked_candidates=["src/trustme/_cli.py:main"],
        source_evidence=["src/trustme/_cli.py:main"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 98
    assert report["semantic_profile_ids"] == ["command_entrypoint_invocation_boundary"]


def test_profiled_pytest_decorator_is_not_treated_as_utility_noise():
    target = "src/pytest_bdd/scenario.py:_get_scenario_decorator"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert report["contract_archetype_ids"] == ["pytest_fixture_or_decorator_registration"]
    assert not any("support/utility target: decorator" in reason for reason in report["reasons"])
