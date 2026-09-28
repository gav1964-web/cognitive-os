from __future__ import annotations

import json
import shutil
from pathlib import Path

from runtime.self_improvement_evolution import proposal_from_diagnosis, run_config_evolution


ROOT = Path(__file__).resolve().parents[2]


def _proposal(value: int = 24) -> dict:
    return {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/executable_acceptance_policy.json",
        "operation": "merge_object",
        "path": "/structural_sample_policy",
        "content": {"maximum_inferred_length": value},
    }


def _result(score: float, *, architect: float | None = None) -> dict:
    return {
        "status": "ok",
        "project_min_score": score,
        "role_scores": {
            "project_analyzer": score,
            "architect": architect if architect is not None else score,
            "spec_writer": score,
        },
    }


def test_evolution_accepts_measured_non_regressing_candidate_without_writing():
    target = ROOT / "config" / "executable_acceptance_policy.json"
    before = target.read_bytes()

    def evaluate(candidate, case):
        return _result(9.2 if candidate is None else 9.4)

    report = run_config_evolution(
        root=ROOT,
        failure_packet={"project": "shadow", "minimum": 9.2},
        proposal=_proposal(),
        shadow_case="shadow",
        regression_cases=["control-a", "control-b"],
        evaluate=evaluate,
    )

    assert report["decision"] == "accepted"
    assert report["gates"]["regression_suite_passed"] is True
    assert report["promotion"]["applied"] is False
    assert target.read_bytes() == before


def test_evolution_atomically_promotes_validated_candidate(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    target = config_dir / "executable_acceptance_policy.json"
    shutil.copyfile(ROOT / "config" / target.name, target)

    def evaluate(candidate, case):
        return _result(9.2 if candidate is None else 9.4)

    report = run_config_evolution(
        root=tmp_path,
        failure_packet={"project": "shadow"},
        proposal=_proposal(19),
        shadow_case="shadow",
        regression_cases=["control"],
        evaluate=evaluate,
        promote=True,
    )

    promoted = json.loads(target.read_text(encoding="utf-8"))
    assert report["decision"] == "accepted"
    assert report["promotion"]["applied"] is True
    assert promoted["structural_sample_policy"]["maximum_inferred_length"] == 19


def test_evolution_rejects_role_regression_even_when_minimum_improves():
    def evaluate(candidate, case):
        return _result(9.2) if candidate is None else _result(9.3, architect=9.1)

    report = run_config_evolution(
        root=ROOT,
        failure_packet={"project": "shadow"},
        proposal=_proposal(),
        shadow_case="shadow",
        regression_cases=[],
        evaluate=evaluate,
    )

    assert report["decision"] == "rejected_evidence"
    assert report["gates"]["no_shadow_role_regression"] is False


def test_evolution_requires_an_independent_regression_case():
    def evaluate(candidate, case):
        return _result(9.2 if candidate is None else 9.4)

    report = run_config_evolution(
        root=ROOT,
        failure_packet={"project": "shadow"},
        proposal=_proposal(),
        shadow_case="shadow",
        regression_cases=[],
        evaluate=evaluate,
    )

    assert report["decision"] == "rejected_evidence"
    assert report["gates"]["regression_suite_passed"] is False


def test_evolution_rejects_source_project_mutation_signal():
    def evaluate(candidate, case):
        result = _result(9.2 if candidate is None else 9.4)
        result["source_project_unchanged"] = candidate is None
        return result

    report = run_config_evolution(
        root=ROOT,
        failure_packet={"project": "shadow"},
        proposal=_proposal(),
        shadow_case="shadow",
        regression_cases=["control"],
        evaluate=evaluate,
    )

    assert report["decision"] == "rejected_evidence"
    assert report["gates"]["source_projects_unchanged"] is False


def test_evolution_rejects_mutation_outside_allowlist_without_evaluation():
    proposal = _proposal()
    proposal["path"] = "/sample_values"

    def evaluate(candidate, case):
        raise AssertionError("blocked proposal must not be evaluated")

    report = run_config_evolution(
        root=ROOT,
        failure_packet={},
        proposal=proposal,
        shadow_case="shadow",
        regression_cases=[],
        evaluate=evaluate,
    )

    assert report["decision"] == "rejected_validation"
    assert "mutation_path_not_allowed" in report["validation"]["validation"]["errors"][0]


def test_evolution_rejects_structurally_valid_but_non_executable_parameter():
    proposal = _proposal()
    proposal["content"] = {"priorities": {"first_slice_selection": {"property_accessor": 0.3}}}

    def evaluate(candidate, case):
        raise AssertionError("non-executable proposal must not be evaluated")

    report = run_config_evolution(
        root=ROOT,
        failure_packet={},
        proposal=proposal,
        shadow_case="shadow",
        regression_cases=[],
        evaluate=evaluate,
    )

    assert report["decision"] == "rejected_validation"
    errors = report["validation"]["validation"]["errors"]
    assert any("mutation_key_not_executable:/structural_sample_policy/priorities/first_slice_selection" in row for row in errors)


def test_proposal_can_be_extracted_from_llm_diagnosis():
    proposal = _proposal()
    diagnosis = {"proposed_knowledge": {"config_mutation_proposal": proposal}}

    assert proposal_from_diagnosis(diagnosis) == proposal
