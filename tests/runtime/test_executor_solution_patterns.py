from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.executor_solution_patterns import load_executor_solution_patterns, select_solution_patterns


ROOT = Path(__file__).resolve().parents[2]


def test_executor_solution_patterns_select_verified_no_patch_pattern():
    selected = select_solution_patterns(
        {
            "acceptance_signal": "executable_callable",
            "patch_synthesis": "skipped",
            "patch_quality_level": "verified_no_patch",
        }
    )

    assert selected[0]["id"] == "executor_pattern_verified_no_patch_callable"
    assert selected[0]["authority"] == "advisory_pattern_only"


def test_executor_solution_patterns_select_stub_completion_pattern():
    selected = select_solution_patterns(
        {
            "patch_synthesis": "prepared",
            "patch_quality_level": "contract_backed_return_literal",
        }
    )

    assert selected[0]["id"] == "executor_pattern_contract_backed_stub_completion"


def test_executor_solution_patterns_select_notimplemented_completion_pattern():
    selected = select_solution_patterns(
        {
            "patch_synthesis": "prepared",
            "patch_quality_level": "contract_backed_notimplemented_return",
        }
    )

    assert selected[0]["id"] == "executor_pattern_contract_backed_notimplemented_completion"


def test_executor_solution_patterns_select_string_transform_pattern():
    selected = select_solution_patterns(
        {
            "patch_synthesis": "prepared",
            "patch_quality_level": "contract_backed_identity_transform",
        }
    )

    assert selected[0]["id"] == "executor_pattern_contract_backed_identity_transform"


def test_executor_solution_patterns_reject_auto_source_mutation(tmp_path: Path):
    payload = json.loads((ROOT / "config" / "executor_solution_patterns.json").read_text(encoding="utf-8"))
    payload["admission_policy"]["automatic_source_mutation_allowed"] = True
    path = tmp_path / "patterns.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="automatic source mutation"):
        load_executor_solution_patterns(path)
