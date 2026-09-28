from __future__ import annotations

import ast

from runtime.source_side_effect_inference import infer_ast_side_effects
from runtime.source_effect_evidence import observed_side_effects


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


def test_pandas_read_sql_is_a_database_read_contract_effect():
    node = ast.parse(
        "def load_table(query, engine):\n    return pd.read_sql(query, engine)\n"
    ).body[0]

    assert "database_read" in infer_ast_side_effects(node, ast.unparse(node))


def test_dataframe_file_transform_declares_read_and_write_effects():
    node = ast.parse(
        "def normalize(input_file, output_file):\n"
        "    frame = pd.read_csv(input_file)\n"
        "    frame.to_csv(output_file, index=False)\n"
    ).body[0]

    effects = infer_ast_side_effects(node, ast.unparse(node))

    assert "filesystem_read" in effects
    assert "filesystem_write" in effects


def test_media_and_serialization_sinks_declare_filesystem_write():
    node = ast.parse(
        "def persist(values, source, target):\n"
        "    sf.write(target, values, 44100)\n"
        "    shutil.copy2(source, target)\n"
        "    pickle.dump(values, target)\n"
    ).body[0]

    assert "filesystem_write" in infer_ast_side_effects(node, ast.unparse(node))


def test_mutating_argument_collection_is_memory_state_effect():
    node = ast.parse("def collect(values, item):\n    values.append(item)\n    return values\n").body[0]

    assert "memory_state" in observed_side_effects(node, [{"name": "values"}, {"name": "item"}])


def test_element_tree_parse_declares_filesystem_read_effect():
    node = ast.parse(
        "def read_tokens(filename):\n"
        "    return xml.etree.ElementTree.parse(filename).getroot()\n"
    ).body[0]

    assert "filesystem_read" in infer_ast_side_effects(node, ast.unparse(node))


def test_terminal_renderer_method_is_an_observability_effect():
    node = ast.parse("def render(qr):\n    qr.print_tty()\n").body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["observability"]


def test_raw_descriptor_io_and_select_are_external_runtime_effects():
    node = ast.parse(
        "def terminal_round_trip(payload):\n"
        "    os.write(1, payload)\n"
        "    select.select([0], [], [], 0.2)\n"
        "    return os.read(0, 32)\n"
    ).body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["external_runtime"]


def test_terminal_widget_render_calls_are_external_runtime_effects():
    node = ast.parse("def redraw(self):\n    self.goto(0, 0)\n    self.wr('ready')\n").body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["external_runtime"]


def test_pure_factory_is_excluded_without_hiding_real_observability():
    factory = ast.parse("def keys():\n    return logging.makeLogRecord({}).__dict__.keys()\n").body[0]
    mixed = ast.parse(
        "def report():\n    logging.makeLogRecord({})\n    logger.info('ready')\n"
    ).body[0]

    assert infer_ast_side_effects(factory, ast.unparse(factory)) == []
    assert infer_ast_side_effects(mixed, ast.unparse(mixed)) == ["observability"]


def test_cache_invalidation_and_module_reload_are_memory_state_effects():
    node = ast.parse(
        "def invalidate(module):\n"
        "    importlib.invalidate_caches()\n"
        "    linecache.clearcache()\n"
        "    cached_lookup.cache_clear()\n"
        "    importlib.reload(module)\n"
    ).body[0]

    assert infer_ast_side_effects(node, ast.unparse(node)) == ["memory_state"]
