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


def test_stdout_and_cprint_are_observability_effects():
    node = ast.parse("def report():\n    print('summary')\n    cprint.info('result')\n").body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["observability"]


def test_redis_membership_lookup_is_network_effect():
    node = ast.parse("async def verify(pool, user):\n    return await pool.sismember('users', user)\n").body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["network"]


def test_local_object_attribute_update_is_not_memory_state_effect():
    node = ast.parse("def build():\n    result = Result()\n    result.value = 1\n    return result\n").body[0]

    assert "memory_state" not in infer_ast_side_effects(node, ast.unparse(node))
