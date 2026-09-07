from pathlib import Path

from runtime.project_development_delta import development_delta_transform
from runtime.project_development_handoff import _focused_project_report
from runtime.project_failure_causal_diagnosis import enrich_failure_diagnosis
from runtime._parts.architecture_decision_builder_part3 import _architecture_synthesis_summary


def _diagnosis(target: str, detail: str, nodeid: str) -> dict:
    return {
        "issues": [{
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contracts",
            "affected_targets": [target],
            "failure_specific_reducer_required": True,
            "failure_evidence": [{
                "target": target,
                "detail": detail,
                "failing_nodeids": [nodeid],
                "failure_signature": "signature",
            }],
            "allowed_operator_ids": [],
        }]
    }


def test_empty_fast_path_creates_training_only_causal_design(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "more.py").write_text(
        "def split_before(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n\n"
        "def split_after(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        "more.py:split_before", "AssertionError: Lists differ: [[]] != []",
        "tests/test_more.py::SplitTests::test_empty_collection",
    )

    result = enrich_failure_diagnosis(
        diagnosis, project_dir=project, workspace_root=Path.cwd()
    )
    issue = result["issues"][0]

    assert issue["causal_hypothesis"]["pattern_id"] == "empty_materialized_fast_path_yield"
    assert issue["causal_hypothesis"]["execution_authority"] is False
    assert issue["repair_design"]["status"] == "proposal_review_required"
    assert issue["allowed_operator_ids"] == []


def test_embedded_numeric_range_creates_boundary_repair_proposal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "factor.py").write_text(
        "import re\n\ndef expand_ranges(value: str) -> str:\n"
        "    return re.sub(r'( \\d+ ) - ( \\d+ )', 'x', value)\n",
        encoding="utf-8",
    )
    diagnosis = _diagnosis(
        "factor.py:expand_ranges", "digits were expanded inside a factor name",
        "tests/test_factor.py::test_range[digit run continuing a factor name is not a range]",
    )

    result = enrich_failure_diagnosis(
        diagnosis, project_dir=project, workspace_root=Path.cwd()
    )

    assert result["issues"][0]["repair_design"]["proposed_operator_id"] == (
        "require_left_token_boundary_for_numeric_range"
    )


def test_training_design_reaches_architect_and_non_executable_spec(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "more.py").write_text(
        "def split_before(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n",
        encoding="utf-8",
    )
    issue = enrich_failure_diagnosis(
        _diagnosis(
            "more.py:split_before", "AssertionError: [[]] != []",
            "tests/test_more.py::SplitTests::test_empty_collection",
        ),
        project_dir=project,
        workspace_root=Path.cwd(),
    )["issues"][0]

    focused = _focused_project_report(
        {"summary": {}, "answers": {"1_scope": {}}}, issue, {}
    )
    assert focused["architecture_synthesis"]["repair_design"]["execution_authority"] is False
    summary = _architecture_synthesis_summary(focused["architecture_synthesis"])
    assert summary["repair_design"]["proposed_operator_id"] == "guard_empty_materialized_fast_path"

    transform = development_delta_transform(
        {"selected_issue": issue, "selected_option": {}}, {}
    )
    spec = transform({
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "more.py:split_before",
            "signature": {"args": [{"name": "iterable", "annotation": "Iterable"}]},
        }],
    })

    assert spec["implementation_delta"]["status"] == "proposal_review_required"
    assert spec["implementation_delta"]["intent"]["operator_id"] == "guard_empty_materialized_fast_path"
    assert spec["extraction_contract"]["allowed_operator_ids"] == []
    assert spec["implementation_handoff"]["mode"] == "proposal_review_required"


def test_explicit_training_replay_authorizes_only_proposed_operator(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "more.py").write_text(
        "def split_before(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n\n"
        "def split_after(iterable, pred, maxsplit=-1):\n"
        "    if maxsplit == 0:\n"
        "        yield list(iterable)\n"
        "        return\n",
        encoding="utf-8",
    )
    issue = enrich_failure_diagnosis(
        _diagnosis(
            "more.py:split_before", "AssertionError: [[]] != []",
            "tests/test_more.py::SplitTests::test_empty_collection",
        ),
        project_dir=project,
        workspace_root=Path.cwd(),
        authorize_training_replay=True,
    )["issues"][0]

    assert issue["allowed_operator_ids"] == ["guard_empty_materialized_fast_path"]
    assert issue["training_replay_authority"]["source_apply"] is False
    assert issue["affected_targets"] == [
        "more.py:split_before", "more.py:split_after"
    ]
    transform = development_delta_transform(
        {"selected_issue": issue, "selected_option": {}}, {}
    )
    spec = transform({
        "artifact_type": "TechnicalSpec",
        "source_evidence": [{
            "source": "more.py:split_before",
            "signature": {"args": [{"name": "iterable", "annotation": "Iterable"}]},
        }],
    })
    assert spec["implementation_delta"]["status"] == "ready"
    assert spec["implementation_delta"]["intent"]["authority"] == "explicit_training_replay"
