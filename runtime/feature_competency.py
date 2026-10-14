"""Compiled-competency route: user goal -> registered task competency -> independent checks.

Opt-in, domain-neutral and model-free. Each competency listed in
`config/task_competencies.json` is asked through the verified knowledge-provider call
for a `task_competency.v1` change. A competency may declare a detector (currently ruff
rules); the runtime then runs the detector on a copy of the project and passes its
diagnostics in the request. Exactly one proposal is qualified by one of two oracles:
  tests     new tests must assertion-fail on the original and pass on the candidate;
  detector  the declared diagnostics disappear at the edited sites, no new diagnostic
            appears in edited files, and (when the change requires it) existing tests
            referencing the edited modules must exist and pass at least once on the original.
In both cases existing tests referencing the edited modules keep identical outcomes.
Refusal or failed qualification returns control to the caller (usually the LLM role
workflow); nothing is installed without `apply_source`.
"""
import json
from collections import Counter
from pathlib import Path, PurePosixPath

from .competency_knowledge import invoke_knowledge
from .feature_acceptance import probe, save
from .feature_workspace import copy_source, digest, install, inventory, owned_path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'config/task_competencies.json'
MAX_SOURCE_BYTES = 400_000
MAX_REGRESSION_FILES = 20


def task_competencies(root=ROOT):
    """Catalog rows as {'capability', 'detector'}; v1 plain ids remain accepted."""
    data = json.loads((Path(root) / CATALOG).read_text(encoding='utf-8'))
    rows = data.get('competencies')
    if data.get('schema_version') not in ('task_competencies.v1', 'task_competencies.v2') or not isinstance(rows, list):
        raise ValueError('invalid_task_competency_catalog')
    result = []
    for row in rows:
        row = {'capability': row} if isinstance(row, str) else dict(row)
        detector = row.get('detector')
        if not isinstance(row.get('capability'), str) or (detector is not None and (
                detector.get('tool') != 'ruff' or not detector.get('rules')
                or not all(isinstance(r, str) and r.isalnum() for r in detector['rules']))):
            raise ValueError('invalid_task_competency_catalog')
        result.append({'capability': row['capability'], 'detector': detector})
    if len({r['capability'] for r in result}) != len(result):
        raise ValueError('invalid_task_competency_catalog')
    return result


def run_competency_first(*, project, work, goal, python, apply_source=False, root=ROOT):
    project, work = Path(project).resolve(), Path(work).resolve()
    if not goal.strip() or work.exists() or work.is_relative_to(project) or project.is_relative_to(work):
        raise ValueError('competency_requires_goal_and_fresh_external_workdir')
    work.mkdir(parents=True)
    report = {'schema_version': 'feature_competency.v2', 'goal': goal, 'project': str(project),
              'route': 'compiled_competency', 'model_calls': 0, 'source_apply': False, 'attempts': []}
    try:
        expected = inventory(project)
        save(work / 'source-inventory.json', expected)
        change = _propose(project, work, goal, expected, report, root)
        if change is None:
            return _finish(work, report)
        report['change'] = {k: change.get(k) for k in ('competency', 'target', 'operator_id', 'acceptance', 'limitations', 'oracle')}
        tests, edits = _materialize(project, expected, change)
        report['frozen_test_hashes'] = {n: digest(b) for n, b in tests.items()}
        regression = _referencing_tests(project, expected, edits)
        report['regression_scope'] = regression
        baseline = _checked_copy(project, work / 'baseline', expected, tests)
        candidate = _checked_copy(project, work / 'candidate', expected, {**tests, **edits})
        if tests:
            reason = _qualify_tests(baseline, candidate, work, python, tests, report)
        else:
            reason = _qualify_detector(project, candidate, work, edits, change, regression, report)
        if reason is None:
            reason = _qualify_regression(baseline, candidate, work, python, regression, report,
                                         require_passing=bool(change.get('requires_regression_tests')))
        if reason:
            report.update(status='blocked', reason=reason)
            return _finish(work, report)
        if inventory(project) != expected:
            raise ValueError('competency_original_source_changed')
        report.update(status='verified', goal_complete=None,
                      limitations=[*change['limitations'], 'Goal completeness is not judged by a model reviewer on this route.'])
        if apply_source:
            report['installation'] = install(project, expected, {**tests, **edits}, work / 'backup')
            report.update(status='installed', source_apply=True)
    except Exception as exc:
        report.update(status='blocked', reason=str(exc), error_type=type(exc).__name__)
    return _finish(work, report)


def _propose(project, work, goal, expected, report, root):
    sources = _python_sources(project, expected)
    diagnostics = None
    proposals = []
    for row in task_competencies(root):
        payload = {'operation': 'task_change', 'goal': goal, 'sources': sources}
        if row['detector']:
            if diagnostics is None:
                try:
                    diagnostics = _detector_diagnostics(project, work, expected)
                except RuntimeError as exc:  # e.g. ruff not installed: skip, do not block other competencies
                    diagnostics = str(exc)
            if isinstance(diagnostics, str):
                report['attempts'].append({'competency': row['capability'], 'status': 'skipped', 'reason': diagnostics})
                continue
            rules = set(row['detector']['rules'])
            payload['diagnostics'] = [d for d in diagnostics if d['code'] in rules]
        result = invoke_knowledge(row['capability'], payload, root=root)
        report['attempts'].append({'competency': row['capability'], 'status': result['status'], 'reason': result.get('reason')})
        if result['status'] == 'proposed':
            proposals.append(result['change'])
    if not proposals:
        report.update(status='not_applicable', reason='no_task_competency_applies')
        return None
    if len(proposals) > 1:
        report.update(status='not_applicable', reason='ambiguous_task_competencies')
        return None
    return proposals[0]


def _detector_diagnostics(project, work, expected):
    from .fix_template_detector import run_ruff
    folder = work / 'detector-input'
    copy_source(project, folder, expected)
    return [{'path': name, 'code': d['code'], 'row': d['row'], 'end_row': d['end_row']}
            for name, rows in run_ruff(folder).items() if name in expected for d in rows]


def _qualify_tests(baseline, candidate, work, python, tests, report):
    red = probe(baseline, work / 'baseline-new', python, list(tests), {})
    report['baseline'] = _summary(red)
    if not _assertion_red(red):
        return 'competency_baseline_not_red'
    green = probe(candidate, work / 'candidate-new', python, list(tests), {})
    report['candidate'] = _summary(green)
    if not (green['returncode'] == 0 and set(green['tests']) == set(red['tests'])
            and all(v == 'passed' for v in green['tests'].values())):
        return 'competency_candidate_not_green'
    return None


def _qualify_detector(project, candidate, work, edits, change, regression, report):
    """Declared diagnostics removed at every claimed site, nothing new in edited files."""
    from .fix_template_detector import run_ruff
    oracle = change.get('oracle') or {}
    if oracle.get('kind') != 'detector' or oracle.get('tool') != 'ruff' or not oracle.get('sites'):
        return 'competency_change_without_supported_oracle'
    if change.get('requires_regression_tests') and not regression:
        return 'competency_requires_regression_tests'
    check = {}
    for label, root in (('before', project), ('after', candidate)):
        folder = work / 'detector-check' / label
        for index, name in enumerate(sorted(edits)):
            target = folder / f'{index}.py'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / name).read_bytes())
        check[label] = run_ruff(folder)
    fixed = Counter((s['path'], s['rule']) for s in oracle['sites'])
    problems = []
    for index, name in enumerate(sorted(edits)):
        before = Counter(d['code'] for d in check['before'].get(f'{index}.py', []))
        after = Counter(d['code'] for d in check['after'].get(f'{index}.py', []))
        for (path, rule), count in fixed.items():
            if path == name and after[rule] != before[rule] - count:
                problems.append(f'{name}:{rule}:{before[rule]}->{after[rule]}')
        new = after - before
        if new:
            problems.append(f'{name}:new:{",".join(sorted(new))}')
    report['detector_check'] = {'sites': len(oracle['sites']), 'problems': problems}
    return 'competency_detector_check_failed' if problems else None


def _qualify_regression(baseline, candidate, work, python, regression, report, *, require_passing=False):
    if not regression:
        return None
    before = probe(baseline, work / 'baseline-regression', python, regression, {})
    if require_passing and not before['counts']['passed']:
        report['regression'] = {'before': before['counts']}
        return 'competency_regression_tests_not_runnable'
    after = probe(candidate, work / 'candidate-regression', python, regression, {})
    report['regression'] = {'before': before['counts'], 'after': after['counts'],
                            'changed': sorted(n for n in set(before['tests']) | set(after['tests'])
                                              if before['tests'].get(n) != after['tests'].get(n))}
    return 'competency_regression_outcome_changed' if report['regression']['changed'] else None


def _finish(work, report):
    save(work / 'report.json', report)
    return report


def _python_sources(project, expected):
    rows = []
    for name in sorted(expected):
        path = project / name
        if name.endswith('.py') and path.stat().st_size <= MAX_SOURCE_BYTES:
            try:
                rows.append({'path': name, 'content': path.read_text(encoding='utf-8')})
            except UnicodeDecodeError:
                continue
    return rows


def _is_test(name):
    parts = PurePosixPath(name).parts
    return any(p in ('tests', 'test') or p.startswith('test_') for p in parts)


def _materialize(project, expected, change):
    tests, edits = {}, {}
    for row in change['tests']:
        name = row['path']
        if name in expected or name in tests or not name.startswith('tests/test_') or not name.endswith('.py'):
            raise ValueError('competency_new_test_path_invalid:' + name)
        owned_path(project, name)
        tests[name] = row['content'].encode('utf-8')
    for row in change['edits']:
        name = row['path']
        if name not in expected or _is_test(name) or not name.endswith('.py') or name in edits:
            raise ValueError('competency_edit_path_invalid:' + name)
        owned_path(project, name)
        edits[name] = row['content'].encode('utf-8')
    if not edits or not (tests or (change.get('oracle') or {}).get('kind') == 'detector'):
        raise ValueError('competency_change_requires_edits_and_an_oracle')
    return tests, edits


def _module_names(name):
    parts = list(PurePosixPath(name).with_suffix('').parts)
    if 'src' in parts:
        parts = parts[len(parts) - parts[::-1].index('src'):]
    if parts and parts[-1] == '__init__':
        parts = parts[:-1]
    return {'.'.join(parts), parts[-1]} if parts else set()


def _referencing_tests(project, expected, edits):
    names = set().union(*(_module_names(n) for n in edits))
    found = []
    for name in sorted(expected):
        if not (_is_test(name) and PurePosixPath(name).name.startswith('test') and name.endswith('.py')):
            continue
        text = (project / name).read_text(encoding='utf-8', errors='replace')
        if any(f'import {m}' in text or f'from {m} ' in text or f'{m}.' in text for m in names if m):
            found.append(name)
    return found[:MAX_REGRESSION_FILES]


def _checked_copy(project, destination, expected, files):
    copy_source(project, destination, expected)
    for name, body in files.items():
        target = owned_path(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return destination


def _assertion_red(result):
    counts = result['counts']
    return (result['returncode'] == 1 and counts['failed'] > 0 and not counts['error'] and not counts['skipped']
            and len(result['assertion_failures']) == counts['failed'] and result['source_unchanged'])


def _summary(result):
    return {k: result[k] for k in ('returncode', 'counts', 'assertion_failures', 'source_unchanged', 'junit')}
