"""Detect unexplained loss of draft test cases; declarations still need audit."""
import ast
from collections import Counter


def cases(artifact):
    result = {}

    def visit(nodes, path, owner=''):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, path, owner + node.name + '::')
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                result[path + '::' + owner + node.name] = owner + node.name

    for test in artifact.get('tests', []):
        try:
            visit(ast.parse(test['content']).body, test['path'])
        except (SyntaxError, KeyError, TypeError):
            continue  # Ordinary artifact validation reports malformed sources.
    return result


def compare_draft(previous, current):
    old, new = cases(previous), cases(current)
    old_names, new_names = Counter(old.values()), Counter(new.values())
    # Moving a uniquely named test between files is not disappearance.
    missing = sorted(key for key, name in old.items() if key not in new
                     and not (old_names[name] == 1 and new_names[name] == 1))
    explained = set()
    mappings = current.get('case_replacements', [])
    if isinstance(mappings, list):
        for row in mappings:
            if not isinstance(row, dict):
                continue
            targets = row.get('replacements')
            if (row.get('previous') in missing and isinstance(row.get('reason'), str)
                    and row['reason'].strip() and isinstance(targets, list) and targets
                    and all(isinstance(name, str) and name in new for name in targets)):
                explained.add(row['previous'])
    unexplained = sorted(set(missing) - explained)
    return {'missing': missing, 'unexplained': unexplained,
            'instruction': 'Retain prior draft test cases while correcting their bodies. File moves with unique test names are allowed. For intentional rename/consolidation provide case_replacements:[{previous:"old/path.py::test_name", replacements:["new/path.py::test_name"], reason:"how required behavior remains covered"}]. A declaration grants no approval: fresh audit must verify replacement assertions; all native checks remain mandatory.'}
