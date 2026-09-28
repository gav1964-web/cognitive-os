"""Compile model-owned JSON call/expectation contracts to standalone pytest tests.

No target-specific fixtures or algorithms. Initial scope: existing module-level
functions taking JSON data and returning JSON-compatible values.
"""
import ast
import hashlib
import json
import pprint
import re
from pathlib import Path

from .feature_workspace import owned_path
from .feature_case_catalog import case_catalog


TEMPLATE = '''import importlib
import json
from pathlib import Path

import pytest

MODULE = {module!r}
FUNCTION = {function!r}
SOURCE = {source!r}
CASES = {cases}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_contract(case):
    module = importlib.import_module(MODULE)
    expected_source = Path(__file__).resolve().parents[1] / SOURCE
    if Path(module.__file__).resolve() != expected_source.resolve():
        raise RuntimeError("contract imported a different source tree")
    result = getattr(module, FUNCTION)(*case.get("args", []), **case.get("kwargs", {{}}))
    result = json.loads(json.dumps(result, allow_nan=False))
    for check in case["checks"]:
        actual = result
        for part in check["path"]:
            if isinstance(actual, dict):
                assert part in actual, f"missing output key: {{part!r}}"
            elif isinstance(actual, list):
                if type(part) is not int:
                    raise ValueError("list path component must be an integer; use op:length for length")
                assert 0 <= part < len(actual), f"missing output index: {{part!r}}"
            else:
                raise AssertionError(f"output cannot be traversed at {{part!r}}: {{actual!r}}")
            actual = actual[part]
        expected = check["expected"]
        if check["op"] == "equals":
            assert actual == expected
        elif check["op"] == "length":
            assert isinstance(actual, (list, dict, str)), "output has no supported length"
            assert len(actual) == expected
        else:
            assert isinstance(actual, (list, dict, str)), "output is not a supported container"
            if check["op"] == "contains":
                assert expected in actual
            else:
                assert expected not in actual
'''


def compile_cases(project, expected, spec, scope):
    cases = spec.get('cases')
    if not isinstance(cases, list) or not 1 <= len(cases) <= 12 or 'tests' in spec:
        raise ValueError('feature_cases_require_1_to_12_cases_not_python_tests')
    if len(json.dumps(cases, ensure_ascii=False, allow_nan=False).encode()) > 24000:
        raise ValueError('feature_cases_data_limit24000_bytes')
    if {c.get('baseline') for c in cases} != {'fails', 'passes'}:
        raise ValueError('feature_cases_declare_baseline_fails_and_passes_variants')
    grouped, names = {}, set()
    menu = case_catalog(project, expected, scope)
    allowed = {row['api']: row['entrypoint'] for row in menu}
    for case in cases:
        name = case.get('id', '')
        entry = allowed.get(case.get('api'), case.get('entrypoint', ''))
        if entry not in allowed.values():
            raise ValueError('feature_case_choose_api_from_menu:' + ','.join(allowed))
        case = {**case, 'entrypoint': entry}
        if (not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name)
                or name in names or not isinstance(entry, str)
                or not re.fullmatch(r'[a-zA-Z]\w*(?:\.[a-zA-Z]\w*)+', entry)):
            raise ValueError('feature_case_unique_id_and_public_entrypoint_required')
        names.add(name)
        module, function = entry.rsplit('.', 1)
        paths = [module.replace('.', '/') + '.py', 'src/' + module.replace('.', '/') + '.py']
        matches = [p for p in paths if p in expected and p in scope]
        if len(matches) != 1:
            raise ValueError('feature_case_entrypoint_outside_design_or_ambiguous:' + entry)
        source = owned_path(Path(project), matches[0])
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        if not any(isinstance(n, ast.FunctionDef) and n.name == function for n in tree.body):
            raise ValueError('feature_case_requires_existing_module_function:' + entry)
        if (not isinstance(case.get('args', []), list) or not isinstance(case.get('kwargs', {}), dict)
                or not isinstance(case.get('checks'), list) or not 1 <= len(case['checks']) <= 12):
            raise ValueError('feature_case_args_kwargs_checks_invalid:' + name)
        for check in case['checks']:
            if (not isinstance(check, dict) or set(check) != {'path', 'op', 'expected'}
                    or not isinstance(check['path'], list) or len(check['path']) > 12
                    or any(type(p) not in (str, int) for p in check['path'])
                    or any(type(p) is int and p < 0 for p in check['path'])
                    or check['op'] not in ('equals', 'length', 'contains', 'not_contains')
                    or check['op'] == 'length' and (type(check['expected']) is not int or check['expected'] < 0)):
                raise ValueError('feature_case_check_invalid:' + name)
        grouped.setdefault((module, function, matches[0]), []).append(case)
    if len(grouped) > 4:
        raise ValueError('feature_cases_max4_entrypoints')
    tests = []
    contract_id = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()[:10]
    for ordinal, ((module, function, source), rows) in enumerate(grouped.items(), 1):
        body = TEMPLATE.format(module=module, function=function, source=source,
                               cases=pprint.pformat(rows, width=100, sort_dicts=False))
        if len(body.splitlines()) > 400:
            raise ValueError('feature_compiled_test_too_large:reduce_case_data:' + module + '.' + function)
        tests.append({'path': f'tests/test_cos_contract_{contract_id}_{ordinal}.py', 'content': body})
    return {**spec, 'tests': tests, 'test_authoring': {
        'cases_and_expectations': 'COS SpecWriter model',
        'python_scaffolding': 'runtime.feature_case_compiler',
        'applicability': 'existing module functions with JSON inputs/output; not full object or file pipeline coverage'}}
