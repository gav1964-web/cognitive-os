"""Conservative module/import bindings for bounded call-impact observations."""
import ast
from collections import Counter
from pathlib import PurePosixPath


def module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


class _Bindings(ast.NodeVisitor):
    def __init__(self):
        self.names = Counter()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names[node.id] += 1

    def visit_FunctionDef(self, node):
        self.names[node.name] += 1

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Import(self, node):
        for alias in node.names:
            self.names[alias.asname or alias.name.split('.')[0]] += 1

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.names[alias.asname or alias.name] += 1

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs


def call_bindings(tree: ast.Module, path: str, known_targets: set[str]) -> list[dict]:
    """Resolve only unique module declarations/imports without lexical shadowing.

    These are static bindings, not runtime identity guarantees. Attribute dispatch,
    import hooks, monkeypatching and external consumers remain unproven.
    """
    counts = _Bindings()
    counts.visit(tree)
    module = module_name(path)
    aliases = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and counts.names[node.name] == 1:
            aliases[node.name] = module + '.' + node.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split('.')[0]
                if counts.names[local] == 1:
                    aliases[local] = alias.name if alias.asname else local
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                package = module.split('.') if path.endswith('/__init__.py') else module.split('.')[:-1]
                if node.level > len(package):
                    continue
                base = '.'.join(package[:len(package) - node.level + 1] + ([base] if base else []))
            for alias in node.names:
                local = alias.asname or alias.name
                if local != '*' and counts.names[local] == 1:
                    aliases[local] = base + '.' + alias.name
    # Dynamic namespace updates and global/nonlocal assignments preclude claims.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                aliases.pop(name, None)
        elif (isinstance(node, ast.ImportFrom) and any(a.name == '*' for a in node.names)) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {'exec', 'eval', 'globals', 'locals'}):
            aliases = {}
    target_names = {}
    for target in known_targets:
        filename, _, symbol = target.partition(':')
        if '.' in symbol:
            continue  # Methods may use descriptors, inheritance or dynamic dispatch.
        target_names.setdefault(module_name(filename) + '.' + symbol, []).append(target)
    rows = []

    class Calls(ast.NodeVisitor):
        blocked = set()

        def visit_FunctionDef(self, node):
            local = _Bindings()
            for statement in node.body:
                local.visit(statement)
            args = node.args
            names = {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
            names.update(a.arg for a in (args.vararg, args.kwarg) if a)
            previous = self.blocked
            self.blocked = previous | names | set(local.names)
            for statement in node.body:
                self.visit(statement)
            self.blocked = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            previous = self.blocked
            # Class namespaces and descriptors are intentionally unresolved.
            self.blocked = set(aliases)
            self.generic_visit(node)
            self.blocked = previous

        def visit_Lambda(self, node):
            previous = self.blocked
            self.blocked = set(aliases)
            self.generic_visit(node)
            self.blocked = previous

        visit_ListComp = visit_Lambda
        visit_SetComp = visit_Lambda
        visit_DictComp = visit_Lambda
        visit_GeneratorExp = visit_Lambda

        def visit_Call(self, node):
            parts = []
            value = node.func
            while isinstance(value, ast.Attribute):
                parts.insert(0, value.attr)
                value = value.value
            resolved = []
            if isinstance(value, ast.Name) and value.id not in self.blocked and value.id in aliases:
                full = '.'.join([aliases[value.id], *parts])
                resolved = target_names.get(full, [])
            if len(resolved) != 1:
                resolved = []
            rows.append({'node': node, 'resolved_targets': resolved})
            self.generic_visit(node)

    Calls().visit(tree)
    return rows
