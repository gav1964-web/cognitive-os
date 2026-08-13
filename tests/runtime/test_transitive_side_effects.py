import ast

from runtime.transitive_side_effects import infer_transitive_side_effects


def test_transitive_side_effects_follow_same_module_method_calls():
    tree = ast.parse(
        "class Dump:\n"
        "    def write_rows(self):\n"
        "        with open('rows.ndjson', 'w') as stream:\n"
        "            stream.write('row')\n"
        "    def dump(self):\n"
        "        self.write_rows()\n"
    )
    target = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "dump")

    report = infer_transitive_side_effects(tree, target)

    assert report["effects"] == ["filesystem_write"]
    assert {tuple(row["call_chain"]) for row in report["chains"]} == {("dump", "write_rows")}


def test_transitive_side_effects_capture_framework_state_updates():
    tree = ast.parse("def change(control):\n    control.set_state(2)\n")
    target = tree.body[0]

    report = infer_transitive_side_effects(tree, target)

    assert report["effects"] == ["memory_state"]


def test_transitive_side_effects_follow_network_session_wrappers():
    tree = ast.parse(
        "class Client:\n"
        "    def _post(self, url):\n"
        "        return self._session.post(url)\n"
        "    def authenticate(self, url):\n"
        "        return self._post(url)\n"
    )
    target = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "authenticate")

    report = infer_transitive_side_effects(tree, target)

    assert report["effects"] == ["network"]
    assert {tuple(row["call_chain"]) for row in report["chains"]} == {("authenticate", "_post")}


def test_transitive_side_effects_capture_exception_hook_observability():
    tree = ast.parse("def report_failure(exc):\n    logger.error(exc)\n")

    report = infer_transitive_side_effects(tree, tree.body[0])

    assert report["effects"] == ["observability"]


def test_side_effects_distinguish_local_mapping_from_receiver_mutation():
    local_tree = ast.parse("def build():\n    result = {}\n    result['x'] = 1\n    return result\n")
    receiver_tree = ast.parse("def update(self):\n    self.value = 1\n")

    local = infer_transitive_side_effects(local_tree, local_tree.body[0])
    receiver = infer_transitive_side_effects(receiver_tree, receiver_tree.body[0])

    assert local["effects"] == []
    assert receiver["effects"] == ["memory_state"]
