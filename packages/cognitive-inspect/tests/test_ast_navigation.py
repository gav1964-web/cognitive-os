import ast

from cognitive_inspect.ast_navigation import find_top_level_function, parent_map


def test_lookup_is_top_level_and_preserves_first_sync_or_async_node():
    tree = ast.parse('class C:\n    def match(): pass\nasync def match(): pass\ndef match(): pass\n')
    assert find_top_level_function(tree, 'match') is tree.body[1]
    assert find_top_level_function(ast.parse('class C:\n    def match(): pass'), 'match') is None
    assert find_top_level_function(tree, 'absent') is None


def test_parent_map_preserves_node_identity_and_does_not_mutate_tree():
    tree = ast.parse('def f(rows):\n    for row in rows:\n        result.append(row)\n')
    before = ast.dump(tree, include_attributes=True)
    parents = parent_map(tree)
    call = tree.body[0].body[0].body[0].value
    assert parents[call] is tree.body[0].body[0].body[0]
    assert parents[parents[call]] is tree.body[0].body[0]
    assert tree not in parents
    assert ast.dump(tree, include_attributes=True) == before
def test_call_name_preserves_attribute_and_unsupported_expression_behavior():
    import ast
    from cognitive_inspect.ast_navigation import call_name
    for text, expected in [('json.dumps', 'json.dumps'), ('value', 'value'),
                           ('factory().write_text', 'write_text'), ('42', '')]:
        node = ast.parse(text, mode='eval').body
        before = ast.dump(node)
        assert call_name(node) == expected
        assert ast.dump(node) == before
