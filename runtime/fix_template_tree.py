"""Uniform AST trees, edit anti-unification and template matching for learned fix templates.

A tree node has a label (AST class name, list field, or primitive field) and ordered
children. Holes (`?n`) stand for any subtree. Anti-unifying two edits (before, after)
uses one substitution table for both sides, so a hole in `after` must be bound by
`before`; otherwise the generalization is not executable and is rejected.
Domain-neutral: no knowledge of particular defects lives here.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

SKIPPED_FIELDS = {'ctx', 'type_comment', 'kind', 'lineno', 'col_offset', 'end_lineno', 'end_col_offset'}


@dataclass(frozen=True)
class Node:
    label: str
    children: tuple = ()
    value: object = None
    key: str = field(default='', compare=False)

    @property
    def is_hole(self) -> bool:
        return self.label.startswith('?')


def _make(label, children=(), value=None):
    children = tuple(children)
    key = label + ('=' + type(value).__name__ + ':' + repr(value) if value is not None or label.startswith('f:') else '')
    if children:
        key += '(' + ','.join(c.key for c in children) + ')'
    return Node(label, children, value, key)


def hole(index: int) -> Node:
    return _make(f'?{index}')


def from_ast(node) -> Node:
    if isinstance(node, list):
        raise TypeError('lists are wrapped by their field')
    children = []
    for name, value in ast.iter_fields(node):
        if name in SKIPPED_FIELDS:
            continue
        if isinstance(value, list):
            children.append(_make('L:' + name, [from_ast(v) if isinstance(v, ast.AST) else _make('f:' + name, value=v)
                                                for v in value]))
        elif isinstance(value, ast.AST):
            children.append(_make('N:' + name, [from_ast(value)]))
        else:
            children.append(_make('f:' + name, value=value))
    return _make(type(node).__name__, children)


def to_ast(tree: Node):
    if tree.is_hole:
        raise ValueError('unbound_hole')
    cls = getattr(ast, tree.label)
    kwargs = {}
    for child in tree.children:
        kind, _, name = child.label.partition(':')
        if kind == 'L':
            kwargs[name] = [c.value if c.label.startswith('f:') else to_ast(c) for c in child.children]
        elif kind == 'N':
            kwargs[name] = to_ast(child.children[0])
        else:
            kwargs[name] = child.value
    result = cls(**kwargs)
    if 'ctx' in cls._fields:
        result.ctx = ast.Load()
    return result


def unparse(tree: Node) -> str:
    node = to_ast(tree)
    _fix_store_contexts(node)
    return ast.unparse(ast.fix_missing_locations(node))


def _fix_store_contexts(node):
    targets = []
    if isinstance(node, (ast.Assign, ast.Delete)):
        targets = node.targets
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    for target in targets:
        for sub in ast.walk(target):
            if hasattr(sub, 'ctx'):
                sub.ctx = ast.Del() if isinstance(node, ast.Delete) else ast.Store()
    for child in ast.iter_child_nodes(node):
        _fix_store_contexts(child)


def size(tree: Node) -> int:
    return 1 + sum(size(c) for c in tree.children)


def concrete_size(tree: Node) -> int:
    return 0 if tree.is_hole else 1 + sum(concrete_size(c) for c in tree.children)


def holes(tree: Node) -> set:
    return {tree.label} if tree.is_hole else set().union(*(holes(c) for c in tree.children)) if tree.children else set()


def _au(a: Node, b: Node, table: dict) -> Node:
    # Hole names are local to each template: identical keys may only short-circuit
    # for hole-free subtrees ('?' in a key is a conservative hole test).
    if a.key == b.key and '?' not in a.key:
        return a
    if not a.is_hole and not b.is_hole and a.label == b.label and len(a.children) == len(b.children) \
            and a.value == b.value and type(a.value) is type(b.value):
        return _make(a.label, [_au(x, y, table) for x, y in zip(a.children, b.children)], a.value)
    pair = (a.key, b.key)
    if pair not in table:
        table[pair] = hole(len(table))
    return table[pair]


def anti_unify_edit(first: tuple, second: tuple):
    """Return the least general (before, after) template covering both edits, or None."""
    table: dict = {}
    before = _au(first[0], second[0], table)
    after = _au(first[1], second[1], table)
    if not holes(after) <= holes(before):
        return None
    return before, after


def match(pattern: Node, tree: Node, binding: dict | None = None):
    binding = {} if binding is None else binding
    if pattern.is_hole:
        bound = binding.get(pattern.label)
        if bound is None:
            binding[pattern.label] = tree
            return binding
        return binding if bound.key == tree.key else None
    if pattern.label != tree.label or len(pattern.children) != len(tree.children) \
            or pattern.value != tree.value or type(pattern.value) is not type(tree.value):
        return None
    for p, t in zip(pattern.children, tree.children):
        if match(p, t, binding) is None:
            return None
    return binding


def substitute(pattern: Node, binding: dict) -> Node:
    if pattern.is_hole:
        return binding[pattern.label]
    if not pattern.children:
        return pattern
    return _make(pattern.label, [substitute(c, binding) for c in pattern.children], pattern.value)


def iter_statements(tree: Node):
    """Yield every statement subtree (elements of statement-list fields)."""
    for child in tree.children:
        if child.label in ('L:body', 'L:orelse', 'L:finalbody', 'L:handlers'):
            for stmt in child.children:
                if not stmt.label.startswith('f:'):
                    yield stmt
                    yield from iter_statements(stmt)
        else:
            yield from iter_statements(child)


def template_text(tree: Node) -> str:
    """Readable template: holes printed as H0, H1, ... where an expression fits."""
    names = {}

    def fill(node):
        if node.is_hole:
            names.setdefault(node.label, f'H{node.label[1:]}')
            return from_ast(ast.Name(id=names[node.label]))
        if not node.children:
            return node
        return _make(node.label, [fill(c) for c in node.children], node.value)
    try:
        return unparse(fill(tree))
    except Exception:
        return tree.key


def to_json(tree: Node):
    """Lossless JSON form of a tree or template (for versioned competency KB)."""
    row = {'l': tree.label}
    if tree.children:
        row['c'] = [to_json(c) for c in tree.children]
    if tree.label.startswith('f:'):
        value = tree.value
        if isinstance(value, bytes):
            row['b'] = value.decode('latin-1')
        elif isinstance(value, complex):
            row['j'] = [value.real, value.imag]
        elif value is Ellipsis:
            row['e'] = True
        else:
            row['v'] = value
    return row


def from_json(row) -> Node:
    if 'b' in row:
        value = row['b'].encode('latin-1')
    elif 'j' in row:
        value = complex(*row['j'])
    elif 'e' in row:
        value = Ellipsis
    else:
        value = row.get('v')
    return _make(row['l'], [from_json(c) for c in row.get('c', [])], value)
