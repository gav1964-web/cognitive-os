from __future__ import annotations

import json
from pathlib import Path

from runtime.executor_corpus_miner import mine_executor_corpus


def test_executor_corpus_miner_stages_fixture_candidate_from_upstream_tests(tmp_path: Path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pkg" / "core.py").write_text("def search(query_vector):\n    return [query_vector]\n", encoding="utf-8")
    (project / "tests" / "test_core.py").write_text("from pkg.core import search\n\nsearch([0.0, 1.0])\n", encoding="utf-8")
    report = {
        "cases": [
            {
                "project": "demo",
                "project_dir": project.as_posix(),
                "acceptance_signal": "meta_only",
                "boundary_track": "fixture_or_runtime_shape_boundary",
                "executor_playbook_ids": ["executor_playbook_fixture_profile_gap"],
                "acceptance_skipped_targets": [
                    {"target": "pkg/core.py:search", "reason": "positive_sample_execution_failed"}
                ],
            }
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    mined = mine_executor_corpus([path])

    candidate = mined["candidates"][0]
    assert mined["policy"]["automatic_kb_promotion_allowed"] is False
    assert candidate["record_type"] == "executor_fixture_profile_candidate"
    assert candidate["upstream_test_refs"] == ["tests/test_core.py"]
    assert candidate["admission"]["auto_promote"] is False


def test_executor_corpus_miner_stages_case_level_solution_candidate(tmp_path: Path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "core.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    report = {
        "cases": [
            {
                "project": "demo",
                "project_dir": project.as_posix(),
                "acceptance_signal": "executable_callable",
                "boundary_track": "pure_python_callable",
                "patch_quality_level": "signature_fallback_guard",
                "patch_synthesis": "prepared",
                "patch_reason": "required_input_guard_synthesized",
                "target": "pkg/core.py:normalize",
                "solution_pattern_ids": ["executor_pattern_signature_fallback_review"],
                "source_code_changes": False,
            }
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    mined = mine_executor_corpus([path])

    candidate = mined["candidates"][0]
    assert candidate["record_type"] == "executor_solution_pattern_candidate"
    assert candidate["evidence"]["solution_pattern_ids"] == ["executor_pattern_signature_fallback_review"]
    assert "def normalize" in candidate["source_excerpt"]


def test_executor_corpus_miner_reads_full_chain_nested_acceptance(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "core.py").write_text("def parse(value):\n    return value\n", encoding="utf-8")
    report = {
        "cases": [
            {
                "project": "nested-demo",
                "project_dir": project.as_posix(),
                "executor": {
                    "acceptance_signal": "meta_only",
                    "acceptance_skipped_targets": [
                        {"target": "core.py:parse", "reason": "positive_sample_execution_failed"}
                    ],
                },
            }
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    mined = mine_executor_corpus([path])

    assert mined["summary"]["candidate_count"] == 1
    assert mined["candidates"][0]["evidence"]["acceptance_signal"] == "meta_only"
