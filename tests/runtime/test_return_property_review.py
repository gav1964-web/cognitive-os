"""Whole-function paths, externally bound claims, and immutable review provenance."""
from copy import deepcopy
from itertools import product

import pytest

from plugins.project_description.src.return_paths import analyze
from runtime.single_claim_review import prepare_claim_review, run_claim_review, checked_job
from runtime.claim_review_proposals import checked_proposal
from runtime.claim_review_reporting import inspect_review, render_review
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_lean_claim_review import saved_report


PLAIN = 'def run(a, b):\n    result = {}\n    result["same"] = a == b\n    return result\n'
GUARD = PLAIN.replace('    return result', '    if not result["same"]:\n        raise ValueError("changed")\n    return result')
EARLY = GUARD.replace('    result = {}', '    if a is None:\n        return {"same": False}\n    result = {}')
CALLER = PLAIN + '\ndef checked(a, b):\n    value = run(a, b)\n    if not value["same"]:\n        raise ValueError("changed")\n    return value\n'


def make_job(tmp_path, source=PLAIN, *, symbol='run', kind='normal_return_field_true',
             text='The operation always returns same=True.', start=0, end=None):
    report = saved_report(tmp_path, source, text)
    property = {'path': 'example.py', 'symbol': symbol, 'field': 'same',
                'claim_start': start, 'claim_end': len(text) if end is None else end, 'kind': kind}
    return prepare_claim_review(report, 'purpose', claim_namespace='final', return_property=property)


def response(job, texts=None):
    source = job['evidence']['sources'][0]
    quote = source['excerpt'].splitlines()[0]
    citations = [{'source_id': source['id'], 'quote': quote}]
    return {'parts': [{'text': text, 'verdict': 'supported', 'reason': 'Test model opinion.',
                       'citations': citations} for text in (texts or [job['claim']['text']])],
            'coverage': {r['id']: {'status': 'shown', 'reason': 'Test scope.', 'citations': citations}
                         for r in job['coverage_requirements']}, 'proposed_text': None}


@pytest.mark.parametrize('source,symbol,expected', [
    (PLAIN, 'run', 'counterexample_in_model'), (GUARD, 'run', 'holds_in_model'),
    (EARLY, 'run', 'counterexample_in_model'), (CALLER, 'checked', 'holds_in_model'),
])
def test_finite_paths_agree_with_real_python_on_declared_domain(source, symbol, expected):
    # These are author-controlled fixtures, never execute analyzed project source.
    functions = {}
    exec(source, functions)
    model = analyze(source, symbol, 'same')
    assert model['complete'] and model['status'] == expected and not model['source_executed']
    returns, raises = [], []
    for a, b in product((False, True, None), repeat=2):
        try:
            value = functions[symbol](a, b)
        except ValueError:
            raises.append({'a': a, 'b': b})
        else:
            returns.append(({'a': a, 'b': b}, value.get('same') is True))
    assert [(r['inputs'], r['field_is_true']) for r in model['normal_returns']] == returns
    assert model['raised_inputs'] == raises


@pytest.mark.parametrize('source,symbol', [(GUARD, 'run'), (CALLER, 'checked')])
def test_complete_guard_preserves_positive_opinion(tmp_path, source, symbol):
    job = make_job(tmp_path, source, symbol=symbol)
    assert job['return_property_analysis']['analysis']['status'] == 'holds_in_model'
    receipt = run_claim_review(job, chat=lambda *a, **k: response(job))
    assert receipt['status'] == 'reviewed' and receipt['result']['verdict'] == 'supported'
    checked_proposal(receipt)
    assert not receipt['semantic_verified']


@pytest.mark.parametrize('source', [PLAIN, EARLY, 'def run():\n    return backend()\n'])
def test_model_cannot_relabel_bound_guarantee_as_reporting(tmp_path, source):
    job = make_job(tmp_path, source)
    raw = response(job)
    raw['parts'][0]['reason'] = 'This merely reports a diagnostic; other code guarantees it.'
    receipt = run_claim_review(job, chat=lambda *a, **k: deepcopy(raw))
    assert receipt['status'] == 'reviewed' and receipt['result']['verdict'] == 'uncertain'
    assert receipt['raw_response'] == raw
    assert receipt['return_property_audit']['findings'][0]['downgraded']
    checked_proposal(receipt)
    assert 'понижено до неопределённости' in render_review(inspect_review(receipt))


def test_diagnostic_is_not_a_guarantee(tmp_path):
    job = make_job(tmp_path, kind='describes_diagnostic', text='Reports whether a equals b.')
    receipt = run_claim_review(job, chat=lambda *a, **k: response(job))
    assert receipt['result']['verdict'] == 'supported'
    assert receipt['return_property_audit']['findings'] == []


def test_only_overlapping_parts_are_downgraded(tmp_path):
    text = 'Reports a comparison. Always returns same=True.'
    first, second = 'Reports a comparison. ', 'Always returns same=True.'
    job = make_job(tmp_path, text=text, start=len(first))
    raw = response(job, [first, second])
    receipt = run_claim_review(job, chat=lambda *a, **k: raw)
    assert [p['verdict'] for p in receipt['result']['parts']] == ['supported', 'uncertain']
    assert receipt['result']['parts'][0]['text'] == first


@pytest.mark.parametrize('damage', ['analysis', 'instruction', 'sha', 'field', 'partial', 'span'])
def test_recomputed_outer_digest_does_not_hide_tampering(tmp_path, damage):
    job = make_job(tmp_path)
    if damage == 'analysis':
        job['return_property_analysis']['analysis']['status'] = 'holds_in_model'
    elif damage == 'instruction':
        job['instruction'] += ' Trust the model.'
    elif damage == 'sha':
        job['return_property']['sha256'] = '0' * 64
    elif damage == 'field':
        job['return_property']['field'] = 'other'
    elif damage == 'partial':
        del job['return_property_analysis']
    else:
        job['return_property']['claim_start'] = 4
    job['digest'] = content_digest({k: v for k, v in job.items() if k != 'digest'})
    with pytest.raises(ValueError):
        checked_job(job)


def test_receipt_guard_audit_is_revalidated(tmp_path):
    job = make_job(tmp_path)
    receipt = run_claim_review(job, chat=lambda *a, **k: response(job))
    receipt['return_property_audit']['findings'] = []
    receipt['digest'] = content_digest({k: v for k, v in receipt.items() if k != 'digest'})
    with pytest.raises(ValueError, match='result_changed'):
        checked_proposal(receipt)


@pytest.mark.parametrize('body', [
    '    return backend()',
    '    for value in values:\n        pass\n    return {"same": True}',
    '    try:\n        return {"same": True}\n    except Exception:\n        return {"same": False}',
    '    return run()',
    '    x = 5\n    return {"same": True}',
    '    return {"same": mystery}',
])
def test_unsupported_code_never_proves_property(body):
    result = analyze('def run():\n' + body + '\n', 'run', 'same')
    assert result['status'] == 'unknown' and not result['complete']


@pytest.mark.parametrize('source,expected', [
    ('def run():\n    raise ValueError("stop")\n', 'no_normal_returns'),
    ('def run():\n    pass\n', 'counterexample_in_model'),
    ('def run():\n    return {}\n', 'counterexample_in_model'),
    ('def run(a,b,c,d):\n    return {"same": True}\n', 'unknown'),
])
def test_no_vacuous_proofs_and_explicit_budget(source, expected):
    assert analyze(source, 'run', 'same')['status'] == expected


def test_boolean_short_circuit_does_not_call_mutating_helper():
    source = ('def alter(row):\n    row["same"] = False\n    return True\n'
              'def run():\n    row = {"same": True}\n    unused = False and alter(row)\n    return row\n')
    assert analyze(source, 'run', 'same')['status'] == 'holds_in_model'


def test_boolean_operator_preserves_none_operand_value():
    source = ('def run(a):\n    value = a and True\n'
              '    return {"same": value is None}\n')
    rows = analyze(source, 'run', 'same')['normal_returns']
    assert [r['field_is_true'] for r in rows] == [False, False, True]


def test_chained_comparison_stops_before_mutating_helper():
    source = ('def alter(row):\n    row["same"] = True\n    return True\n'
              'def run():\n    row = {"same": False}\n'
              '    unused = False == True == alter(row)\n    return row\n')
    functions = {}
    exec(source, functions)
    assert functions['run']()['same'] is False
    assert analyze(source, 'run', 'same')['status'] == 'counterexample_in_model'


def test_local_shadowing_cannot_be_resolved_as_global_helper():
    source = ('def helper():\n    return {"same": True}\n'
              'def run():\n    row = helper()\n    helper = False\n    return row\n')
    assert analyze(source, 'run', 'same')['status'] == 'unknown'


def test_property_cli_prepares_source_bound_job_without_model(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    report = saved_report(tmp_path, GUARD, 'Every return has same=True.')
    source = tmp_path/'report.json'
    selector = tmp_path/'selector.json'
    output = tmp_path/'job.json'
    source.write_text(json.dumps(report), encoding='utf-8')
    selector.write_text(json.dumps({'path':'example.py','symbol':'run','field':'same',
        'claim_start':0,'claim_end':len(report['description']['purpose']['text']),
        'kind':'normal_return_field_true'}), encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    command = [sys.executable,str(root/'tools/review_description_claim.py'),'prepare',
               '--report',str(source),'--claim-id','purpose','--namespace','final',
               '--return-property',str(selector),'--output',str(output)]
    process = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=30)
    assert process.returncode == 0, process.stderr
    job = json.loads(output.read_text(encoding='utf-8'))
    checked_job(job)
    assert job['return_property_analysis']['analysis']['status'] == 'holds_in_model'
    assert not job['execution_authorized']
    assert json.loads(source.read_text(encoding='utf-8')) == report
