import ast
import json

from runtime.promoted_candidate_selection_policies import (
    apply_preflight_selection_policies, apply_selection_policies,
)
from runtime.source_contract_semantics import infer_source_contract


def test_fixture_readiness_orders_simple_output_before_runtime_object(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "fixture-ready",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "candidate_ordering": "executable_fixture_readiness",
            "preflight_trigger_requirements": {
                "observed_side_effects": "nonempty",
                "output_inference_basis": ["explicit_none_annotation"],
            },
            "structural_requirements": {
                "min_return_paths": 1,
                "forbidden_output_inference_basis": ["explicit_none_annotation"],
                "no_observed_side_effects": True,
            },
        }],
    }), encoding="utf-8")
    ranked = [
        _candidate("app.py:emit", "def emit(value: str) -> None:\n    print(value)"),
        _candidate(
            "app.py:normalize_ts",
            "def normalize_ts(value: str) -> datetime.datetime:\n    return datetime.datetime.now()",
        ),
        _candidate("app.py:is_ready", "def is_ready() -> bool:\n    return True"),
    ]

    result = apply_preflight_selection_policies(ranked, path=str(path))

    assert [row["source"] for row in result] == [
        "app.py:is_ready", "app.py:normalize_ts", "app.py:emit",
    ]


def test_fixture_readiness_orders_post_acceptance_reselection(tmp_path):
    path = _policy_path(tmp_path)
    ranked = [
        _candidate(
            "app.py:normalize_ts",
            "def normalize_ts(value: str) -> datetime.datetime:\n    return datetime.datetime.now()",
        ),
        _candidate("app.py:is_ready", "def is_ready() -> bool:\n    return True"),
    ]

    result = apply_selection_policies(
        ranked,
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {}},
        path=str(path),
    )

    assert [row["source"] for row in result] == ["app.py:is_ready", "app.py:normalize_ts"]


def test_fixture_readiness_does_not_promote_property_over_callable(tmp_path):
    path = _policy_path(tmp_path)
    property_row = _candidate(
        "app.py:current", "def current() -> dict:\n    return {'ready': True}"
    )
    property_row["property_accessor"] = True
    callable_row = _candidate(
        "app.py:normalize", "def normalize(value: str) -> str:\n    return value.strip()"
    )

    result = apply_selection_policies(
        [property_row, callable_row],
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {}},
        path=str(path),
    )

    assert [row["source"] for row in result] == [
        "app.py:normalize", "app.py:current",
    ]
    assert not property_row.get("selection_policy_ids")


def test_fixture_readiness_prefers_independent_callable_over_receiver_fixture(tmp_path):
    path = _policy_path(tmp_path)
    receiver = _candidate(
        "app.py:Dialog.render", "def render() -> str:\n    return 'ready'"
    )
    receiver["receiver_independent"] = False
    function = _candidate(
        "app.py:transform", "def transform() -> str:\n    return 'ready'"
    )
    function["receiver_independent"] = True

    result = apply_selection_policies(
        [receiver, function],
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {}},
        path=str(path),
    )

    assert [row["source"] for row in result] == ["app.py:transform", "app.py:Dialog.render"]


def test_fixture_readiness_prefers_projection_over_complex_protocol_input(tmp_path):
    path = _policy_path(tmp_path)
    parser = _candidate(
        "app.py:parse", "def parse(node) -> list:\n    return list(node.children)"
    )
    parser["argument_usage_types"] = {"node": "ProtocolLike"}
    projection = _candidate(
        "app.py:Parser.classes", "def classes() -> list:\n    return []"
    )
    projection["receiver_independent"] = False

    result = apply_selection_policies(
        [parser, projection],
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {}},
        path=str(path),
    )

    assert [row["source"] for row in result] == ["app.py:Parser.classes", "app.py:parse"]


def _policy_path(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "fixture-ready-postflight",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "candidate_ordering": "executable_fixture_readiness",
            "structural_requirements": {
                "min_return_paths": 1,
                "forbidden_output_inference_basis": ["explicit_none_annotation"],
                "no_observed_side_effects": True,
            },
        }],
    }), encoding="utf-8")
    return path


def _candidate(source, snippet):
    function = ast.parse(snippet).body[0]
    signature = {
        "args": [
            {"name": arg.arg, "annotation": ast.unparse(arg.annotation) if arg.annotation else ""}
            for arg in function.args.args
        ],
        "returns": ast.unparse(function.returns) if function.returns else "",
    }
    evidence = {"signature": signature, "snippet": snippet}
    return {
        **infer_source_contract(evidence),
        "source": source,
        "kind": "function",
        "signature": signature,
        "snippet": snippet,
        "evidence": evidence,
    }
