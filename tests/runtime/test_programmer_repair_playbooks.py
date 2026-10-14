from __future__ import annotations

from runtime.programmer_repair_playbooks import (
    classify_verifier_failures,
    repair_recipe_errors,
    select_repair_playbooks,
)
from runtime.programmer_repair_strategy import _messages


def _result(detail: str) -> dict:
    return {
        "executable_acceptance_result": {
            "summary": {
                "skipped_targets": [
                    {
                        "target": "pkg/names.py:hostname",
                        "reason": "positive_sample_execution_failed",
                        "detail": detail,
                    }
                ]
            }
        }
    }


def test_classifies_duplicate_delimiter_from_exact_counterexample():
    result = _result("expected={'return_value': 'desk.example.org'}; got='desk..example.org'")

    failures = classify_verifier_failures(result)
    playbooks = select_repair_playbooks(result)

    assert failures[0]["class"] == "duplicate_delimiter"
    assert playbooks[0]["id"] == "executor_playbook_duplicate_delimiter_repair"
    assert playbooks[0]["authority"] == "advisory_playbook_only"


def test_does_not_classify_unrelated_value_mismatch():
    result = _result("expected={'return_value': 'desk.example.org'}; got='other.example.org'")

    assert classify_verifier_failures(result) == []
    assert select_repair_playbooks(result) == []


def test_classifies_non_alphanumeric_boundary_noise():
    result = _result("expected={'return_value': 'hello_world_test'}; got='_hello_world_test-_' ")

    assert classify_verifier_failures(result)[0]["class"] == "boundary_noise"
    assert select_repair_playbooks(result)[0]["action"] == "repair_output_boundary_normalization"


def test_classifies_lost_numeric_component():
    result = _result("expected={'return_value': [2, 4, 7]}; got=[2, 4, 0]")

    assert classify_verifier_failures(result)[0]["class"] == "numeric_component_loss"
    assert select_repair_playbooks(result)[0]["action"] == "repair_numeric_token_extraction"


def test_classifies_internal_separator_structure_mismatch():
    result = _result("expected={'return_value': 'hello_world_test'}; got='helloworldtest-'")

    assert classify_verifier_failures(result)[0]["class"] == "separator_structure_mismatch"
    assert select_repair_playbooks(result)[0]["action"] == "repair_separator_structure"


def test_repair_prompt_carries_selected_kb_guidance():
    playbook = select_repair_playbooks(
        _result("expected={'return_value': 'desk.example.org'}; got='desk..example.org'")
    )[0]

    messages = _messages({"target": "pkg/names.py:hostname", "repair_playbooks": [playbook]})

    assert "repair_playbooks" in messages[0]["content"]
    assert "normalize delimiters contributed by both adjacent fragments" in messages[1]["content"]


def test_duplicate_delimiter_playbook_rejects_rstrip_only_recipe():
    playbook = select_repair_playbooks(
        _result("expected={'return_value': 'desk.example.org'}; got='desk..example.org'")
    )
    recipe = {
        "replacement_source": "def hostname(domain):\n    return domain.rstrip('.')",
        "edits": [],
    }

    assert repair_recipe_errors(recipe, playbook) == ["one_sided_boundary_normalization"]
    recipe["replacement_source"] = "def hostname(domain):\n    return domain.strip('.')"
    assert repair_recipe_errors(recipe, playbook) == []


def test_boundary_noise_playbook_rejects_split_one_sided_strip_calls():
    playbook = select_repair_playbooks(
        _result("expected={'return_value': 'desk.example.org'}; got='desk.example.org.'")
    )
    recipe = {
        "replacement_source": (
            "def hostname(host, domain):\n"
            "    return host.rstrip('.') + '.' + domain.lstrip('.')"
        ),
        "edits": [],
    }

    assert repair_recipe_errors(recipe, playbook) == ["one_sided_boundary_normalization"]
    recipe["replacement_source"] = (
        "def hostname(host, domain):\n"
        "    return host.rstrip('.') + '.' + domain.lstrip('.').rstrip('.')"
    )
    assert repair_recipe_errors(recipe, playbook) == []
