"""Trusted-copy pytest probe: code identities and call paths, never argument values.

Executed as a standalone script under -I. Only synchronous ordinary methods of
one source-owned class are supported. The receipt is development evidence, not
an attestation against hostile project code.
"""
import ast
import hashlib
import json
import sys
import types
from pathlib import Path


def code_digest(code):
    # marshal's reference/interning flags differ between compiled and imported
    # code. Compare structural bytecode facts, independent of object sharing.
    fields = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
              'co_stacksize', 'co_flags', 'co_name', 'co_firstlineno', 'co_names',
              'co_varnames', 'co_freevars', 'co_cellvars')
    body = {name: getattr(code, name) for name in fields}
    body.update(bytecode=code.co_code.hex(), constants=[constant_key(c) for c in code.co_consts])
    body['exception_table'] = getattr(code, 'co_exceptiontable', b'').hex()
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode('utf-8')).hexdigest()


def constant_key(value):
    if isinstance(value, types.CodeType):
        return ['code', code_digest(value)]
    if isinstance(value, (tuple, frozenset)):
        items = [constant_key(v) for v in value]
        return [type(value).__name__, sorted(items, key=repr) if isinstance(value, frozenset) else items]
    return [type(value).__name__, repr(value)]


def compiled_identities(code):
    result = {(code.co_firstlineno, code.co_name, code_digest(code))}
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            result.update(compiled_identities(value))
    return result


def method_catalog(source, target):
    if len(source.encode('utf-8')) > 1_000_000:
        raise ValueError('method_source_budget_exceeded')
    path, _, symbol = target.partition(':')
    parts = symbol.split('.')
    if len(parts) != 2:
        raise ValueError('ordinary_class_method_required')
    tree = ast.parse(source)
    owners = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == parts[0]]
    if len(owners) != 1:
        raise ValueError('unique_class_required')
    owner = owners[0]
    if (owner.decorator_list or owner.keywords or
            any(not isinstance(n, ast.Name) or n.id != 'object' for n in owner.bases)):
        raise ValueError('ordinary_class_required')
    compiled = compile(source, path, 'exec', dont_inherit=True)
    owner_codes = [c for c in compiled.co_consts if isinstance(c, types.CodeType) and c.co_name == owner.name]
    if len(owner_codes) != 1:
        raise ValueError('unique_class_code_required')
    codes = [c for c in owner_codes[0].co_consts if isinstance(c, types.CodeType)]
    result = {}
    for node in owner.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        args = [*node.args.posonlyargs, *node.args.args]
        if node.decorator_list or not args or args[0].arg != 'self':
            continue
        if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(node)):
            continue
        matches = [c for c in codes if c.co_name == node.name and c.co_firstlineno == node.lineno]
        if len(matches) != 1 or node.name in result:
            raise ValueError('ambiguous_method_definition')
        result[node.name] = {'target': path + ':' + owner.name + '.' + node.name,
            'line_start': node.lineno, 'line_end': node.end_lineno,
            'code_digest': code_digest(matches[0]), 'source': ast.get_source_segment(source, node)}
    if parts[1] not in result or len(result) > 64:
        raise ValueError('method_catalog_unsupported_or_over_budget')
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
                and node.attr in result):
            raise ValueError('method_attribute_mutated')
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {'setattr', 'delattr', 'exec'}):
            raise ValueError('dynamic_method_mutation_unsupported')
    return result


def failing_call_ranges(tree, failure_line, observed_method=None):
    """Select direct assertions or one untouched local return assignment per side.

    This is a deliberately narrow syntactic link, not general data flow. Keep
    every candidate range so two executed calls still fail the uniqueness gate.
    """
    assertions = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)
                  and failure_line is not None and n.lineno <= failure_line <= n.end_lineno]
    ranges = [(n.lineno, n.end_lineno) for n in assertions]
    if len(assertions) != 1:
        return ranges
    assertion = assertions[0]
    owners = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and assertion in n.body]
    test = assertion.test
    if len(owners) != 1 or not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return ranges
    prior = owners[0].body[:owners[0].body.index(assertion)]
    for operand in [test.left, *test.comparators]:
        if not isinstance(operand, ast.Name):
            continue
        name = operand.id
        if sum(isinstance(n, ast.Name) and n.id == name for n in ast.walk(test)) != 1:
            continue
        if any(isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names
               for statement in prior for n in ast.walk(statement)):
            continue
        assignments = [n for n in prior if
            (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id == name) or
            (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name)]
        if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Call):
            continue
        assignment = assignments[0]
        calls = [n for n in ast.walk(assignment.value) if isinstance(n, ast.Call)]
        allowed = [assignment.value]
        if isinstance(assignment.value.func, ast.Attribute) and isinstance(assignment.value.func.value, ast.Call):
            if assignment.value.func.attr == observed_method:
                allowed.append(assignment.value.func.value)
        if any(call not in allowed for call in calls):
            continue
        # Rebinding, aliasing, mutation, nested scopes, or another statement on
        # this line make a line-only trace insufficient to identify the value.
        if any(isinstance(n, ast.Name) and n.id == name for statement in prior
               if statement is not assignment for n in ast.walk(statement)):
            continue
        if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(assignment.value)):
            continue
        if any(statement is not assignment and statement.lineno <= assignment.end_lineno
               and assignment.lineno <= statement.end_lineno for statement in prior):
            continue
        ranges.append((assignment.lineno, assignment.end_lineno))
    return ranges


class TracePlugin:
    def __init__(self, project, target):
        self.project, self.target = project, target
        self.path = (project / target.partition(':')[0]).resolve()
        self.catalog = method_catalog(self.path.read_text(encoding='utf-8'), target)
        self.verified_codes = compiled_identities(compile(
            self.path.read_text(encoding='utf-8'), str(self.path), 'exec', dont_inherit=True))
        self.identities = {(v['line_start'], k): v for k, v in self.catalog.items()}
        self.rows, self.selected = [], []
        self.current, self.active = None, None
        self.old_profile = None

    def reject(self, frame, reason):
        row = self.active['row']
        row['unsupported'] = True
        note = {'symbol': frame.f_code.co_name, 'line': frame.f_code.co_firstlineno, 'reason': reason}
        if note not in row['unsupported_calls'] and len(row['unsupported_calls']) < 16:
            row['unsupported_calls'].append(note)

    def pytest_collection_finish(self, session):
        self.selected = [item.nodeid for item in session.items]

    def profile(self, frame, event, arg):
        if self.current is None or event not in ('call', 'return'):
            return
        if event == 'return':
            if self.active is not None and frame is self.active['frame']:
                self.active = None
            return
        if Path(frame.f_code.co_filename) != self.path:
            if (self.active is not None and frame.f_locals.get('self') is self.active['receiver']):
                self.reject(frame, 'same_receiver_outside_owned_class')
            return
        identity = self.identities.get((frame.f_code.co_firstlineno, frame.f_code.co_name))
        fingerprint = code_digest(frame.f_code)
        verified = (frame.f_code.co_firstlineno, frame.f_code.co_name, fingerprint) in self.verified_codes
        if identity and fingerprint != identity['code_digest']:
            identity = None
        if identity and identity['target'] == self.target:
            if self.active is not None or len(self.current['invocations']) >= 128:
                self.current['unsupported'] = True
                return
            caller = frame.f_back
            while caller and Path(caller.f_code.co_filename) != self.current['test_path']:
                caller = caller.f_back
            if caller is None:
                return
            invocation = {'test_line': caller.f_lineno, 'methods': [self.target], 'edges': [],
                          'unsupported': False, 'unsupported_calls': []}
            self.current['invocations'].append(invocation)
            self.active = {'frame': frame, 'receiver': frame.f_locals.get('self'), 'row': invocation, 'calls': 0}
        elif self.active is not None:
            self.active['calls'] += 1
            if self.active['calls'] > 50000:
                self.active['row']['unsupported'] = True
                return
            if identity is None:
                if not verified:
                    self.reject(frame, 'unrecognized_source_code')
                return
            if frame.f_locals.get('self') is not self.active['receiver']:
                self.reject(frame, 'different_receiver')
                return
            caller = frame.f_back
            parent = None
            while caller is not None:
                if (Path(caller.f_code.co_filename) == self.path
                        and caller.f_locals.get('self') is self.active['receiver']):
                    parent = self.identities.get((caller.f_code.co_firstlineno, caller.f_code.co_name))
                    if parent and code_digest(caller.f_code) != parent['code_digest']:
                        parent = None
                    if parent is not None:
                        break
                caller = caller.f_back
            if parent is None:
                self.reject(frame, 'unrecognized_parent_code')
                return
            row = self.active['row']
            if identity['target'] not in row['methods']:
                row['methods'].append(identity['target'])
            edge = [parent['target'], identity['target']]
            if edge not in row['edges']:
                row['edges'].append(edge)

    def begin_call(self, item):
        self.current = {'nodeid': item.nodeid, 'test_path': Path(str(item.path)).resolve(),
                        'invocations': [], 'unsupported': False}
        self.active = None
        self.old_profile = sys.getprofile()
        if self.old_profile is not None:
            self.current['unsupported'] = True
        sys.setprofile(self.profile)

    def end_call(self):
        intact = sys.getprofile() == self.profile
        sys.setprofile(self.old_profile)
        if self.current is not None and not intact:
            self.current['unsupported'] = True
        self.active = None

    def report(self, item, call, report):
        if call.when != 'call' or self.current is None:
            return
        row = self.current
        failure_line = None
        if call.excinfo is not None and call.excinfo.type is AssertionError:
            entries = [e for e in call.excinfo.traceback if Path(str(e.path)).resolve() == row['test_path']]
            if entries:
                failure_line = entries[-1].lineno + 1
        tree = ast.parse(row['test_path'].read_text(encoding='utf-8'))
        ranges = failing_call_ranges(tree, failure_line, self.target.rsplit('.', 1)[-1])
        relevant = [inv for inv in row['invocations'] if any(
            start <= inv['test_line'] <= end for start, end in ranges)]
        self.rows.append({'nodeid': item.nodeid, 'outcome': report.outcome,
            'failure_line': failure_line, 'invocations': relevant,
            'supported': report.failed and len(relevant) == 1 and not row['unsupported']
                         and not relevant[0]['unsupported']})
        self.current = None


def main():
    import pytest
    project, target, output, arguments = sys.argv[1:]
    project = Path(project).resolve()
    sys.path[:0] = [str(project), str(project / 'src')]
    tracker = TracePlugin(project, target)

    class Hooks:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_call(self, item):
            tracker.begin_call(item)
            try:
                yield
            finally:
                tracker.end_call()

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            outcome = yield
            tracker.report(item, call, outcome.get_result())

    code = pytest.main(json.loads(arguments), plugins=[tracker, Hooks()])
    Path(output).write_text(json.dumps({'selected': tracker.selected, 'rows': tracker.rows}), encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
