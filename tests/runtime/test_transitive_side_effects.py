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
