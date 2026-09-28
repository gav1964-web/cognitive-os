"""Freeze model-authored acceptance, compare both versions and preserve evidence."""
import ast
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .feature_workspace import owned_path, inventory, copy_source, digest, permitted

MAX_TEST_FILES = 8


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def validate_spec(spec, expected):
    tests = {}
    for row in spec['tests']:
        name, body = row['path'], row['content']
        if (name in expected or name in tests or not name.startswith('tests/test_')
                or not name.endswith('.py') or not permitted(name)):
            raise ValueError('feature_new_tests_required')
        owned_path(Path.cwd(), name)
        tree = ast.parse(body)
        violations = []
        if len(body.splitlines()) > 400:
            violations.append(f'file has {len(body.splitlines())} lines; limit400; split into <={MAX_TEST_FILES} test files')
        patch_names = {'patch'} | {a.asname or a.name for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and n.module in ('unittest.mock', 'mock')
            for a in n.names if a.name == 'patch'}
        imported = {a.asname or a.name for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) for a in n.names}
        replaces_behavior = any(
            (isinstance(n, ast.Call) and (
                isinstance(n.func, ast.Name) and n.func.id in patch_names | {'globals', 'locals', 'eval', 'exec'}
                or isinstance(n.func, ast.Attribute) and (n.func.attr == 'patch'
                    or n.func.attr == 'object' and isinstance(n.func.value, ast.Name)
                    and n.func.value.id in patch_names)))
            or (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in imported)
            or (isinstance(n, ast.arg) and n.arg in ('monkeypatch', 'mocker'))
            for n in ast.walk(tree))
        if replaces_behavior:
            violations.append('production replacement forbidden: no patch/monkeypatch, globals or rebinding imports; input-only Mock fixtures are allowed, but real production functions must execute')
        if violations:
            raise ValueError('feature_test_contract:' + name + ':' + '; '.join(violations))
        has_assertion = any(isinstance(n, ast.Assert) or
            (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr.startswith('assert') and len(n.func.attr) > 6)
            for n in ast.walk(tree))
        if (not has_assertion
                or any(word in body for word in ('importorskip', 'pytest.skip', 'pytest.mark.skip',
                                                'pytest.mark.xfail', 'unittest.skip'))):
            raise ValueError('feature_tests_require_assertions_without_skips')
        tests[name] = body.encode('utf-8')
    if not 1 <= len(tests) <= MAX_TEST_FILES:
        raise ValueError('feature_test_file_count')
    regression = spec['regression_tests']
    if not isinstance(regression, list) or len(regression) > 20:
        raise ValueError('feature_existing_regression_required')
    if not regression:
        if (spec.get('regression_policy') != 'new_preservation_only'
                or any(Path(n).name.startswith('test_') and n.endswith('.py') for n in expected)):
            raise ValueError('feature_existing_regression_required')
    for node in regression:
        name = node.partition('::')[0]
        if (name not in expected or not name.endswith('.py')
                or not Path(name).name.startswith('test_')):
            raise ValueError('feature_regression_not_existing_test')
    env = spec.get('environment', {})
    if not isinstance(env, dict) or any(
            not k.endswith('_ROOT') or not k.replace('_', '').isalnum()
            or v != '{sandbox}' for k, v in env.items()):
        raise ValueError('feature_environment_only_project_root_bindings')
    if not spec.get('acceptance') or not spec.get('limitations'):
        raise ValueError('feature_acceptance_and_limits_required')
    return tests


def _parse_junit(path):
    rows = {}
    for node in ET.parse(path).getroot().iter('testcase'):
        key = node.get('classname', '') + '::' + node.get('name', '')
        if key in rows:
            raise ValueError('feature_duplicate_test_identity')
        rows[key] = ('error' if node.find('error') is not None else
                     'failed' if node.find('failure') is not None else
                     'skipped' if node.find('skipped') is not None else 'passed')
    return rows


def probe(project, control, python, targets, environment, *, timeout=120):
    control.mkdir(parents=True, exist_ok=False)
    before = inventory(project)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    env.pop('PYTHONPATH', None)
    env.pop('PYTEST_ADDOPTS', None)
    for key in list(env):
        if key.endswith(('_PARENT_PID', '_PARENT_URL')):
            env.pop(key)
    env.update({k: str(project) for k in environment})
    xml = control / 'tests.xml'
    config = next((project / n for n in ('pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg')
                   if (project / n).is_file()), control / 'pytest.ini')
    if config.parent == control:
        config.write_text('[pytest]\n', encoding='utf-8')
    args = ['-v', '-p', 'no:cacheprovider', '-c', str(config), '--rootdir', str(project),
            '-o', 'pythonpath=src .', '-o', 'addopts=',
            '-o', f'faulthandler_timeout={max(1, min(60, timeout // 2))}',
            '--basetemp', str(control / 'tmp'), '--junitxml', str(xml), *targets]
    contracts = control / 'exception-contracts.json'
    plugin = Path(__file__).with_name('feature_exception_assertions.py').resolve()
    bootstrap = ('import sys,json,importlib.util;from pathlib import Path;p=Path(sys.argv[1]);'
                 'sys.path[:0]=[str(p),str(p/"src")];import pytest;'
                 's=importlib.util.spec_from_file_location("cos_exception_contracts",sys.argv[3]);'
                 'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                 'raise SystemExit(pytest.main(json.loads(sys.argv[2]),'
                 'plugins=[m.ExceptionContracts(p,sys.argv[4])]))')
    command = [str(python), '-I', '-c', bootstrap, str(project), json.dumps(args),
               str(plugin), str(contracts)]
    try:
        run = subprocess.run(command, cwd=project, env=env, capture_output=True,
                             encoding='utf-8', errors='replace', timeout=timeout)
        stdout, stderr, code = run.stdout, run.stderr, run.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = str(exc.stdout or ''), 'test_timeout', -1
    (control / 'output.log').write_text(stdout + stderr, encoding='utf-8')
    rows = _parse_junit(xml) if xml.exists() else {}
    assertion_failures = []
    expected_failures = set(json.loads(contracts.read_text(encoding='utf-8'))) if contracts.exists() else set()
    if xml.exists():
        for node in ET.parse(xml).getroot().iter('testcase'):
            failure = node.find('failure')
            identity = node.get('classname', '') + '::' + node.get('name', '')
            if failure is not None and ('AssertionError' in (failure.text or '')
                    or identity in expected_failures
                    or failure.get('message', '').lstrip().startswith(('assert ', 'Failed: DID NOT RAISE '))):
                assertion_failures.append(node.get('classname', '') + '::' + node.get('name', ''))
    return {'returncode': code, 'tests': rows,
            'counts': {s: list(rows.values()).count(s) for s in ('passed', 'failed', 'error', 'skipped')},
            'source_unchanged': inventory(project) == before, 'assertion_failures': assertion_failures,
            'output_tail': (stdout + stderr)[-14000:], 'junit': str(xml)}


def prepare(project, work, expected, spec, python):
    tests = validate_spec(spec, expected)
    baseline = work / 'baseline'
    copy_source(project, baseline, expected)
    for name, body in tests.items():
        target = owned_path(baseline, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    new = probe(baseline, work / 'baseline-new', python, list(tests), spec.get('environment', {}))
    regression = (probe(baseline, work / 'baseline-regression', python,
                        spec['regression_tests'], spec.get('environment', {}))
                  if spec['regression_tests'] else {
                      'returncode': 0, 'tests': {},
                      'counts': dict(passed=0, failed=0, error=0, skipped=0),
                      'source_unchanged': True, 'assertion_failures': [],
                      'output_tail': '', 'junit': '',
                      'scope': 'No existing test_*.py suite; new model-authored preservation only.'})
    result = {'new_tests': new, 'regression': regression,
              'test_hashes': {n: digest(b) for n, b in tests.items()}}
    case_matches = True
    if spec.get('test_authoring', {}).get('python_scaffolding') == 'runtime.feature_case_compiler':
        result['case_baselines'] = []
        for case in spec['cases']:
            observed = [status for name, status in new['tests'].items() if name.endswith('[' + case['id'] + ']')]
            wanted = 'failed' if case['baseline'] == 'fails' else 'passed'
            result['case_baselines'].append({'id': case['id'], 'expected': wanted, 'observed': observed})
            case_matches = case_matches and observed == [wanted]
    save(work / 'baseline.json', result)
    if (new['returncode'] != 1 or not new['counts']['failed'] or new['counts']['error']
            or len(new['assertion_failures']) != new['counts']['failed']
            or new['counts']['skipped'] or not new['source_unchanged']
            or regression['returncode'] != 0
            or not (regression['counts']['passed'] if spec['regression_tests'] else new['counts']['passed'])
            or regression['counts']['skipped'] or not regression['source_unchanged'] or not case_matches):
        raise ValueError('feature_baseline_not_qualified')
    return tests, result


def execution_feedback(row):
    """Keep every failing test identity and error, omit repeated source tracebacks."""
    summary = {k: row[k] for k in ('returncode', 'counts', 'source_unchanged',
                                  'assertion_failures', 'junit')}
    failures = {}
    xml = Path(row['junit'])
    if xml.is_file():
        for case in ET.parse(xml).getroot().iter('testcase'):
            for node in [*case.findall('error'), *case.findall('failure')]:
                message = node.get('message') or (node.text or '')[-1200:]
                message = message[:1200]
                identity = case.get('classname', '') + '::' + case.get('name', '')
                failures.setdefault(message, []).append(identity)
    summary['failures'] = [{'message': k, 'tests': v} for k, v in failures.items()]
    if not row['tests']:
        summary['output_tail'] = row['output_tail'][-2500:]
    return summary


def specification_feedback(baseline):
    result = {name: execution_feedback(baseline[name]) for name in ('new_tests', 'regression')}
    if 'case_baselines' in baseline:
        result['case_baselines'] = baseline['case_baselines']
    return result


def review_baseline_context(baseline, checked):
    """Losslessly reference repeated green outcomes through the candidate test map."""
    result = {name: {k: v for k, v in baseline[name].items() if k != 'output_tail'}
              for name in ('new_tests', 'regression')}
    new, old, current = (baseline['new_tests']['tests'], baseline['regression']['tests'], checked['tests'])
    if (checked.get('passed') is True and not set(new) & set(old)
            and set(current) == set(new) | set(old) and old
            and all(status == current[name] == 'passed' for name, status in old.items())):
        result['regression'].pop('tests')
        result['regression']['test_outcomes_reference'] = (
            'Exactly verification.tests excluding baseline.new_tests.tests; disjoint partition checked. '
            'Every omitted baseline regression outcome equals its candidate outcome.')
    return result


def verify(project, work, expected, tests, edits, spec, baseline, python):
    candidate = work / 'project'
    copy_source(project, candidate, expected)
    for name, body in {**tests, **edits}.items():
        target = owned_path(candidate, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    result = probe(candidate, work / 'checks', python,
                   [*tests, *spec['regression_tests']], spec.get('environment', {}))
    identities = set(baseline['new_tests']['tests']) | set(baseline['regression']['tests'])
    result['passed'] = (result['returncode'] == 0 and result['source_unchanged']
                        and set(result['tests']) == identities
                        and all(v == 'passed' for v in result['tests'].values()))
    result['candidate_hashes'] = {n: digest(b) for n, b in {**tests, **edits}.items()}
    save(work / 'verification.json', result)
    return result
