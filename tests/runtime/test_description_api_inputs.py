"""Concrete invocation semantics and immutable source-bound claim review."""
from copy import deepcopy

import pytest

from plugins.project_description.src.api_inputs import analyze_inputs
from runtime.single_claim_review import prepare_claim_review, run_claim_review, checked_job
from runtime.claim_review_proposals import checked_proposal
from runtime.narrow_type_evidence_binding import content_digest
from tests.runtime.test_lean_claim_review import saved_report
from tests.runtime.test_return_property_review import response


REQUIRED = '''def execute(*, profile=None):
    if profile is None:
        raise ValueError('profile required')
    return {'ready': True}
'''


@pytest.mark.parametrize('source,inputs,outcome', [
    (REQUIRED, {}, 'raises'), (REQUIRED, {'profile': None}, 'raises'),
    (REQUIRED, {'profile': True}, 'normal_return'),
    (REQUIRED.replace('profile=None', 'profile=True'), {}, 'normal_return'),
    ('def execute(*, profile):\n    return profile\n', {}, 'argument_binding_error'),
    ('def execute(profile=None):\n    return profile\n', {}, 'normal_return'),
    ('def execute():\n    return True\n', {'profile': True}, 'argument_binding_error'),
])
def test_matches_actual_python_for_author_controlled_inputs(source, inputs, outcome):
    model = analyze_inputs(source, 'execute', inputs)
    namespace = {}
    exec(source, namespace)  # Only test fixtures, never inspected project source.
    try:
        namespace['execute'](**inputs)
    except TypeError:
        actual = 'argument_binding_error'
    except ValueError:
        actual = 'raises'
    else:
        actual = 'normal_return'
    assert model['outcome'] == actual == outcome
    assert model['complete'] and not model['source_executed']


@pytest.mark.parametrize('source', [
    'def execute(profile=None):\n    return backend(profile)\n',
    'def execute(profile=make_default()):\n    return True\n',
    'def execute(profile=None):\n    try:\n        return True\n    finally:\n        return backend(profile)\n',
    'def execute(profile=None, /):\n    return True\n',
    'def execute(*args):\n    return True\n',
    'def execute(profile=None):\n    return helper(profile)\ndef helper(profile=True):\n    return True\n',
    'def execute(profile=None):\n    return profile.missing\n',
])
def test_unknown_never_becomes_normal_return(source):
    result = analyze_inputs(source, 'execute', {})
    assert result['status'] == 'unknown' and not result['complete']


def job_for(tmp_path, source=REQUIRED, inputs=None):
    text = 'The API works with omitted profile.'
    report = saved_report(tmp_path, source, text)
    selector = {'path': 'example.py', 'symbol': 'execute', 'kind': 'normal_return_for_inputs',
                'inputs': {} if inputs is None else inputs, 'claim_start': 0, 'claim_end': len(text)}
    return prepare_claim_review(report, 'purpose', claim_namespace='final', return_property=selector)


@pytest.mark.parametrize('source,verdict', [
    (REQUIRED, 'uncertain'), (REQUIRED.replace('profile=None', 'profile=True'), 'supported'),
    ('def execute(profile=None):\n    return backend(profile)\n', 'uncertain'),
])
def test_model_cannot_infer_accepted_default_from_signature(tmp_path, source, verdict):
    job = job_for(tmp_path, source)
    raw = response(job)
    raw['parts'][0]['reason'] = 'Signature has default, so API needs no profile.'
    receipt = run_claim_review(job, chat=lambda *a, **k: deepcopy(raw))
    assert receipt['status'] == 'reviewed'
    assert receipt['result']['verdict'] == verdict
    assert receipt['raw_response'] == raw
    checked_proposal(receipt)


def test_altered_inputs_invalidate_saved_job_even_with_new_outer_digest(tmp_path):
    job = job_for(tmp_path)
    job['return_property']['inputs'] = {'profile': True}
    job.pop('digest')
    job['digest'] = content_digest(job)
    with pytest.raises(ValueError, match='return_property_evidence_or_instruction_changed'):
        checked_job(job)


@pytest.mark.parametrize('inputs', [{'profile': 1}, {'profile': []}, {'bad-key': True}])
def test_only_named_boolean_none_inputs_are_accepted(tmp_path, inputs):
    with pytest.raises(ValueError):
        job_for(tmp_path, inputs=inputs)


def test_cli_selector_preserves_empty_inputs(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    report = saved_report(tmp_path, REQUIRED, 'Works without profile.')
    report_path, selector_path, output = [tmp_path / n for n in ('report.json', 'selector.json', 'job.json')]
    report_path.write_text(json.dumps(report), encoding='utf-8')
    selector_path.write_text(json.dumps({'path': 'example.py', 'symbol': 'execute',
        'kind': 'normal_return_for_inputs', 'inputs': {}, 'claim_start': 0, 'claim_end': 22}), encoding='utf-8')
    root = Path(__file__).resolve().parents[2]
    run = subprocess.run([sys.executable, str(root/'tools/review_description_claim.py'),
        'prepare', '--report', str(report_path), '--claim-id', 'purpose', '--namespace', 'final',
        '--return-property', str(selector_path), '--output', str(output)],
        cwd=root, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    job = json.loads(output.read_text(encoding='utf-8'))
    checked_job(job)
    assert job['return_property_analysis']['analysis']['outcome'] == 'raises'
