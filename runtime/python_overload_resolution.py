"""Recognize contiguous typing overload declarations, never arbitrary duplicates."""
import ast


def implementation_candidates(tree, candidates):
    if len(candidates) < 2 or not all(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in candidates):
        return candidates
    aliases = {}
    for node in getattr(tree,'body',[]):
        if isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name in ('typing','typing_extensions'):
                    aliases[alias.asname or alias.name] = 'module'
        elif isinstance(node,ast.ImportFrom) and node.module in ('typing','typing_extensions') and not node.level:
            for alias in node.names:
                if alias.name == 'overload':
                    aliases[alias.asname or alias.name] = 'decorator'
    # Conservatively refuse shadowed imports, including conditional/local writes.
    writes = {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del))}
    writes |= {n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
    imported = []
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            imported.extend(a.asname or a.name.split('.')[0] for a in node.names)
    if '*' in imported:
        return candidates
    writes |= {name for name in imported if imported.count(name)>1}
    aliases = {name:kind for name,kind in aliases.items() if name not in writes}
    def overload(node):
        return ((isinstance(node,ast.Name) and aliases.get(node.id)=='decorator') or
            (isinstance(node,ast.Attribute) and node.attr=='overload' and isinstance(node.value,ast.Name)
             and aliases.get(node.value.id)=='module'))
    if any(overload(d) for d in candidates[-1].decorator_list):
        return candidates
    for node in candidates[:-1]:
        if (len(node.decorator_list)!=1 or not overload(node.decorator_list[0]) or len(node.body)!=1
                or not (isinstance(node.body[0],ast.Pass) or isinstance(node.body[0],ast.Expr)
                        and isinstance(node.body[0].value,ast.Constant) and node.body[0].value.value is Ellipsis)):
            return candidates
    # Overload stubs and implementation must share one unconditional lexical body.
    for owner in ast.walk(tree):
        if not isinstance(owner,(ast.Module,ast.ClassDef)):
            continue
        body=owner.body
        if candidates[0] in body:
            index=body.index(candidates[0])
            if body[index:index+len(candidates)] == candidates:
                return [candidates[-1]]
    return candidates
