from __future__ import annotations

import ast

from runtime.source_side_effect_inference import infer_ast_side_effects


def test_generated_sdk_call_api_is_a_network_effect():
    node = ast.parse(
        "def create_attachment(client, payload):\n"
        "    return client.call_api('/attachments', 'POST', body=payload)\n"
    ).body[0]

    assert "network" in infer_ast_side_effects(node, ast.unparse(node))


def test_metric_increment_is_observability_effect():
    node = ast.parse("def record():\n    requests_total.labels('ok').inc()\n").body[0]

    assert "observability" in infer_ast_side_effects(node, ast.unparse(node))
