from __future__ import annotations

from pathlib import Path

from tools.github_full_chain_probe import _quality_score, _run_case, run_probe
from tools.github_full_chain_scoring import (
    bounded_quality_score,
    executor_evidence_ready,
    is_controlled_block,
    selected_target_quality,
)


def test_github_full_chain_probe_marks_rust_workspace_out_of_scope(tmp_path):
    projects = tmp_path / "projects"
    project = projects / "rust_workspace"
    (project / ".git").mkdir(parents=True)
    (project / "crates" / "core").mkdir(parents=True)
    (project / "python").mkdir()
    (project / "Cargo.toml").write_text("[workspace]\nmembers=['crates/core']\n", encoding="utf-8")
    for index in range(8):
        (project / "crates" / "core" / f"lib_{index}.rs").write_text("fn main() {}\n", encoding="utf-8")
    (project / "python" / "template.py").write_text("def helper():\n    return 'embedded'\n", encoding="utf-8")

    case = _run_case(project)
    report = run_probe(root=Path.cwd(), projects_dir=projects, label="test_full_chain")

    assert case["status"] == "out_of_scope"
    assert case["source_code_changes"] is False
    assert report["status"] == "needs_review"
    assert report["summary"]["out_of_scope"] == 1
    assert report["summary"]["ready_by_worst_case"] is False


def test_github_full_chain_quality_score_uses_worst_failed_check():
    checks = [{"code": f"C{index}", "passed": True} for index in range(14)]
    checks.append({"code": "target_chain_preserved", "passed": False})

    score = _quality_score(checks)

    assert score < 1.0
    assert score >= 0.92


def test_github_full_chain_quality_score_fails_when_multiple_contract_checks_fail():
    checks = [{"code": f"C{index}", "passed": True} for index in range(12)]
    checks.extend(
        [
            {"code": "target_chain_preserved", "passed": False},
            {"code": "implementation_bound_to_spec", "passed": False},
            {"code": "review_conformance_passed", "passed": False},
        ]
    )

    assert _quality_score(checks) < 0.92


def test_github_full_chain_quality_is_bounded_by_selected_contract_quality():
    checks = [{"code": "chain", "passed": True}]

    assert bounded_quality_score(checks, {"score": 76}) == 0.76


def test_github_full_chain_recognizes_explicit_controlled_block():
    spec = {"extraction_contract": {"status": "blocked_no_safe_candidate"}}
    plan = {"contract_binding": {"binding_status": "blocked_no_safe_candidate"}}

    assert is_controlled_block(spec, plan, []) is True
    assert is_controlled_block(spec, plan, ["tests/test_api.py:run"]) is False


def test_full_chain_target_quality_preserves_spec_structural_evidence():
    target = "pkg/formatting.py:render_name"
    spec = {
        "extraction_contract": {
            "candidate": target,
            "ranked_candidates": [{"source": target}],
            "selection_reason": "pure transform",
            "structural_evidence": {
                "source_body_complete": True,
                "argument_count": 1,
                "explicit_return_annotation": "str",
                "return_paths": 1,
                "observed_side_effects": [],
            },
            "input_contract": {"name": "str"},
            "output_contract": {"result": "str"},
            "side_effects": {"declared": []},
        },
        "source_evidence": [{"source": target}],
    }

    quality = selected_target_quality(spec, "sample-project")

    assert quality["structural_evidence"]["source_body_complete"] is True
    assert quality["score"] > 76


def test_meta_only_acceptance_is_not_executable_evidence():
    meta = {
        "executor_status": "ok",
        "executable_acceptance": "passed",
        "acceptance_signal": "meta_only",
        "callable_harness_count": 0,
    }
    callable_result = {
        **meta,
        "acceptance_signal": "executable_callable",
        "callable_harness_count": 1,
    }

    assert executor_evidence_ready(meta) is False
    assert executor_evidence_ready(callable_result) is True
