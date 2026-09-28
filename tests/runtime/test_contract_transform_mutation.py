import ast

from runtime.contract_transform_mutation import identity_mutation_source, observed_operator


def _function(source: str) -> ast.FunctionDef:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_observed_operator_uses_configured_ast_expression() -> None:
    node = _function("def normalize(value: str) -> str:\n    return value.strip().lower()\n")

    assert observed_operator(node, "value") == "strip_lower"


def test_observed_operator_rejects_similar_unregistered_behavior() -> None:
    node = _function("def normalize(value):\n    return value.casefold()\n")

    assert observed_operator(node, "value") is None


def test_identity_mutation_preserves_signature_name_and_removes_operator() -> None:
    node = _function("def normalize(value: str) -> str:\n    return value.strip().lower()\n")

    source = identity_mutation_source(node, "value")

    assert source == "def normalize(value):\n    return value"
