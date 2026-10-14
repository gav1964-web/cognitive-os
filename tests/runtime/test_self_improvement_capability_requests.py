from pathlib import Path

from runtime.self_improvement_capability_request import capability_development_requests


def _report(project: str, effect: str, basis: str, attempt: dict | None = None) -> dict:
    return {
        "project": project,
        "knowledge_candidate_path": f"{project}.json",
        "diagnosis": {
            "failure_class": "side_effectful_target",
            "target_roles": ["architect", "spec_writer"],
        },
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": [effect] if effect else [],
                "output_inference_basis": basis,
            }},
        },
        "trial_conclusion": {
            "recommended_change_type": "none",
            "next_hypothesis": "continue_bounded_parameter_search",
        },
        "improvement_plugin_cycle": {"attempts": [attempt] if attempt else []},
    }


def test_capability_request_does_not_merge_different_portable_signatures(tmp_path: Path):
    reports = [
        _report("one", "memory_state", "no_value_return"),
        _report("two", "filesystem_read", "return_expression"),
        _report("three", "", "explicit_return_annotation"),
    ]

    assert capability_development_requests(tmp_path, reports, minimum_projects=3) == []


def test_repeated_discriminator_blocks_request_a_plugin_across_void_syntaxes(tmp_path: Path):
    reports = []
    for index, basis in enumerate((
        "no_value_return", "no_value_return", "explicit_none_annotation",
    )):
        reports.append(_report(
            f"project_{index}", "memory_state", basis, {
                "plugin_id": "candidate_selection_admission",
                "status": "blocked" if index else "not_applicable",
                "reason": "no_structural_discriminator" if index else "measured_challenger_missing",
            },
        ))

    requests = capability_development_requests(
        tmp_path, reports, minimum_projects=3,
        signature_normalization={"output_basis_families": {
            "void_side_effect": ["no_value_return", "explicit_none_annotation"],
        }},
    )

    assert len(requests) == 1
    assert requests[0]["missing_capability"] == "candidate_selection_structural_discriminator_synthesis"
    assert requests[0]["observed_projects"] == ["project_0", "project_1", "project_2"]


def test_shadow_success_with_blocked_post_admission_requests_discriminator(tmp_path: Path):
    reports = []
    for index in range(3):
        report = _report(
            f"project_{index}", "", "explicit_return_annotation", {
                "plugin_id": "candidate_selection_discriminator",
                "status": "trial_passed",
            },
        )
        report["post_training_admission"] = {"attempts": [{
            "plugin_id": "candidate_selection_admission",
            "status": "blocked",
            "reason": "no_structural_discriminator",
        }]}
        reports.append(report)

    requests = capability_development_requests(tmp_path, reports, minimum_projects=3)

    assert len(requests) == 1
    assert requests[0]["missing_capability"] == "candidate_selection_structural_discriminator_synthesis"


def test_discriminator_request_keeps_executable_failure_families_separate(tmp_path: Path):
    reports = []
    details = [
        "mismatched embedding dimensions (2 != 3)",
        "got _SafeMethodAttribute instead of str",
        "unsupported operand type(s) for |: '_StubObject'",
    ]
    for index, detail in enumerate(details):
        report = _report(
            f"project_{index}", "", "explicit_return_annotation", {
                "plugin_id": "candidate_selection_admission",
                "status": "blocked",
                "reason": "no_structural_discriminator",
            },
        )
        report["baseline"]["downstream_evidence"]["summary"] = {
            "skipped_targets": [{
                "reason": "positive_sample_execution_failed", "detail": detail,
            }],
        }
        reports.append(report)

    assert capability_development_requests(tmp_path, reports, minimum_projects=3) == []
