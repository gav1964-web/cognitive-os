from __future__ import annotations

from runtime.local_inference import LocalInferenceConfig
from runtime.local_inference import LocalInferenceError
from runtime.programmer_composite_retry import retry_composite_payload


def test_composite_retry_records_schema_rejection_and_result():
    diagnostics = {}
    retry = retry_composite_payload(
        evidence={
            "target": "main.py:run",
            "source_excerpt": "def run(): pass",
            "change_targets": [
                {"target": "main.py:run", "source_excerpt": "def run(): pass"},
                {"target": "helper.py:value", "source_excerpt": "def value(): pass"},
            ],
        },
        normalized={"action": "block_for_review", "patch_recipe_hypothesis": {}},
        initial_payload={},
        messages=[],
        config=LocalInferenceConfig(base_url="http://example.test/v1", model="test"),
        caller=lambda messages, config: {
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "composite",
                "target_symbol": "main.py:run",
                "edit_format": "replace_functions",
                "edits": [
                    {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 2"},
                    {"target_symbol": "helper.py:value", "replacement_source": "def value():\n    return 3"},
                ],
            },
        },
        diagnostics=diagnostics,
    )

    assert retry["action"] == "propose_patch_recipe"
    assert diagnostics["attempted"] is True
    assert diagnostics["status"] == "received"
    assert diagnostics["result_action"] == "propose_patch_recipe"
    assert "composite_recipe_not_proposed" in diagnostics["rejection_errors"]


def test_composite_retry_decomposes_invalid_retry_into_target_recipes():
    diagnostics = {}
    responses = iter(
        [
            {},
            {
                "action": "propose_patch_recipe",
                "patch_recipe_hypothesis": {
                    "recipe_type": "targeted",
                    "target_symbol": "main.py:run",
                    "edit_format": "replace_functions",
                    "edits": [
                        {"target_symbol": "main.py:run", "replacement_source": "def run():\n    return 2"}
                    ],
                },
            },
            {
                "action": "propose_patch_recipe",
                "patch_recipe_hypothesis": {
                    "recipe_type": "targeted",
                    "target_symbol": "helper.py:value",
                    "edit_format": "replace_function",
                    "replacement_source": "def value():\n    return 3",
                },
            },
        ]
    )
    retry = retry_composite_payload(
        evidence={
            "target": "main.py:run",
            "source_excerpt": "def run():\n    return 1",
            "acceptance_obligations": [],
            "change_targets": [
                {"target": "main.py:run", "source_excerpt": "def run():\n    return 1"},
                {"target": "helper.py:value", "source_excerpt": "def value():\n    return 1"},
            ],
        },
        normalized={"action": "block_for_review", "patch_recipe_hypothesis": {}},
        initial_payload={},
        messages=[{"role": "system", "content": "return JSON"}],
        config=LocalInferenceConfig(base_url="http://example.test/v1", model="test"),
        caller=lambda messages, config: next(responses),
        diagnostics=diagnostics,
    )

    edits = retry["patch_recipe_hypothesis"]["edits"]
    assert [item["target_symbol"] for item in edits] == ["main.py:run", "helper.py:value"]
    assert diagnostics["status"] == "decomposed"


def test_target_decomposition_retries_non_json_response_once():
    valid = lambda target, source: {
        "action": "propose_patch_recipe",
        "patch_recipe_hypothesis": {
            "recipe_type": "targeted",
            "target_symbol": target,
            "edit_format": "replace_function",
            "replacement_source": source,
        },
    }
    responses = iter(
        [
            {},
            valid("main.py:run", "def run():\n    return 2"),
            LocalInferenceError("not json"),
            valid("helper.py:value", "def value():\n    return 3"),
        ]
    )

    def caller(messages, config):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    diagnostics = {}
    retry = retry_composite_payload(
        evidence={
            "target": "main.py:run",
            "source_excerpt": "def run():\n    return 1",
            "acceptance_obligations": [],
            "change_targets": [
                {"target": "main.py:run", "source_excerpt": "def run():\n    return 1"},
                {"target": "helper.py:value", "source_excerpt": "def value():\n    return 1"},
            ],
        },
        normalized={"action": "block_for_review", "patch_recipe_hypothesis": {}},
        initial_payload={},
        messages=[{"role": "system", "content": "return JSON"}],
        config=LocalInferenceConfig(base_url="http://example.test/v1", model="test"),
        caller=caller,
        diagnostics=diagnostics,
    )

    assert retry["action"] == "propose_patch_recipe"
    assert diagnostics["status"] == "decomposed"


def test_single_target_semantic_noop_gets_one_corrective_retry():
    diagnostics = {}
    retry = retry_composite_payload(
        evidence={
            "target": "main.py:run",
            "source_excerpt": "def run():\n    return 1",
            "change_targets": [{"target": "main.py:run", "source_excerpt": "def run():\n    return 1"}],
            "repair_playbooks": [{"id": "boundary_repair"}],
        },
        normalized={
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "repair",
                "target_symbol": "main.py:run",
                "edit_format": "replace_function",
                "replacement_source": "def run():\n    return 1",
            },
        },
        initial_payload={"action": "propose_patch_recipe"},
        messages=[{"role": "system", "content": "return JSON"}],
        config=LocalInferenceConfig(base_url="http://example.test/v1", model="test"),
        caller=lambda messages, config: {
            "action": "propose_patch_recipe",
            "patch_recipe_hypothesis": {
                "recipe_type": "repair",
                "target_symbol": "main.py:run",
                "edit_format": "replace_function",
                "replacement_source": "def run():\n    return 2",
            },
        },
        diagnostics=diagnostics,
    )

    assert retry["patch_recipe_hypothesis"]["replacement_source"].endswith("return 2")
    assert diagnostics["rejection_errors"] == ["replacement_semantic_noop"]


def test_single_target_correction_retries_contract_violation_once_more():
    responses = iter(
        [
            {
                "action": "propose_patch_recipe",
                "patch_recipe_hypothesis": {
                    "recipe_type": "repair",
                    "target_symbol": "main.py:wrong_name",
                    "replacement_source": "def wrong_name():\n    return 2",
                },
            },
            {
                "action": "propose_patch_recipe",
                "patch_recipe_hypothesis": {
                    "recipe_type": "repair",
                    "target_symbol": "main.py:run",
                    "replacement_source": "def run():\n    return 2",
                },
            },
        ]
    )
    diagnostics = {}
    retry = retry_composite_payload(
        evidence={
            "target": "main.py:run",
            "source_excerpt": "def run():\n    return 1",
            "change_targets": [{"target": "main.py:run", "source_excerpt": "def run():\n    return 1"}],
        },
        normalized={"action": "block_for_review", "patch_recipe_hypothesis": {}},
        initial_payload={},
        messages=[{"role": "system", "content": "return JSON"}],
        config=LocalInferenceConfig(base_url="http://example.test/v1", model="test"),
        caller=lambda messages, config: next(responses),
        diagnostics=diagnostics,
    )

    assert retry["patch_recipe_hypothesis"]["target_symbol"] == "main.py:run"
    assert "target_symbol_mismatch" in diagnostics["secondary_rejection_errors"]
    assert diagnostics["status"] == "secondary_received"
