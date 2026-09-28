"""Check exception flow against CPython on author-owned contrast fixtures."""
from copy import deepcopy

import pytest

from plugins.project_description.src.api_inputs import analyze_inputs
from runtime.single_claim_review import run_claim_review
from tests.runtime.test_success_api_contracts import job
from tests.runtime.test_return_property_review import response


CASES = [
    ('def run(profile=None):\n    try:\n        if profile is None:\n            raise ValueError("required")\n        return {"status":"ok"}\n    except ValueError:\n        return {"status":"blocked"}\n', {}, 'blocked'),
    ('def run(profile=None):\n    try:\n        if profile is None:\n            profile = True\n    except ValueError:\n        return {"status":"blocked"}\n    else:\n        return {"status":"ok"}\n', {}, 'ok'),
    ('def validate(profile):\n    if profile is None:\n        raise ValueError("missing")\n    return True\ndef run(profile=None):\n    try:\n        validate(profile)\n        return {"status":"ok"}\n    except (ValueError, RuntimeError):\n        return {"status":"blocked"}\n', {}, 'blocked'),
    ('def run():\n    try:\n        raise TypeError("wrong")\n    except ValueError:\n        return {"status":"blocked"}\n', {}, 'raises'),
    ('def run():\n    try:\n        return {"status":"ok"}\n    finally:\n        return {"status":"cancelled"}\n', {}, 'cancelled'),
    ('def run():\n    result = {"status":"ok"}\n    try:\n        return result\n    finally:\n        result["status"] = "changed"\n', {}, 'changed'),
    ('def run():\n    try:\n        raise TypeError("wrong")\n    finally:\n        return {"status":"ok"}\n', {}, 'ok'),
    ('def run():\n    try:\n        raise TypeError("wrong")\n    except:\n        return {"status":"caught"}\n', {}, 'caught'),
    ('def run():\n    try:\n        raise ValueError("wrong")\n    except ValueError:\n        raise RuntimeError("handler")\n    finally:\n        pass\n', {}, 'raises'),
]


@pytest.mark.parametrize('source,inputs,expected', CASES)
def test_status_and_exception_flow_match_python(source, inputs, expected):
    scope = {}
    exec(source, scope)  # Literal test fixtures only.
    try:
        observed = scope['run'](**inputs)['status']
    except (ValueError, RuntimeError, TypeError):
        observed = 'raises'
    assert observed == expected
    result = analyze_inputs(source, 'run', inputs, success={'field':'status','expected':expected})
    assert result['complete'] and not result['source_executed']
    if expected == 'raises':
        assert result['outcome'] == 'raises'
        assert result['status'] == 'counterexample_in_model'
    else:
        assert result['field_matches'] and result['status'] == 'holds_in_model'


@pytest.mark.parametrize('source', [
    'def run():\n    try:\n        return external()\n    except:\n        return {"status":"ok"}\n',
    'def run():\n    try:\n        if "unsupported truth":\n            pass\n    finally:\n        return {"status":"ok"}\n',
    'def run():\n    try:\n        raise ValueError("x")\n    except Exception:\n        return {"status":"ok"}\n',
    'def run():\n    try:\n        raise ValueError("x")\n    except ValueError as error:\n        return {"status":"ok"}\n',
    'def run():\n    raise\n',
    'def run(ValueError):\n    raise ValueError("shadowed")\n',
])
def test_unknown_semantics_cannot_be_hidden_by_handlers_or_finally(source):
    inputs = {'ValueError':None} if 'run(ValueError)' in source else {}
    result = analyze_inputs(source, 'run', inputs, success={'field':'status','expected':'ok'})
    assert result['status'] == 'unknown' and not result['complete']


def test_review_blocks_error_status_but_preserves_valid_default(tmp_path):
    for index in (0, 1):
        source = CASES[index][0].replace('def run(', 'def execute(')
        folder = tmp_path / str(index)
        folder.mkdir()
        selected = job(folder, code=source)
        raw = response(selected)
        report = run_claim_review(selected, chat=lambda *a, **k:deepcopy(raw))
        assert report['raw_response'] == raw
        assert report['result']['verdict'] == ('uncertain' if index == 0 else 'supported')


@pytest.mark.parametrize('default,inputs,expected', [
    ('None', {}, 'blocked'), ('True', {}, 'ready'),
    ('True', {'profile': None}, 'blocked'), ('None', {'profile': False}, 'ready'),
])
def test_default_success_and_reported_flag_are_separate_properties(default, inputs, expected):
    source = ('def validate(profile):\n    if profile is None:\n        raise ValueError("missing")\n    return True\n'
        f'def execute(profile={default}, unchanged=False):\n    try:\n        validate(profile)\n'
        '        return {"status":"ready", "source_unchanged":unchanged}\n'
        '    except ValueError:\n        return {"status":"blocked", "source_unchanged":unchanged}\n')
    namespace = {}
    exec(source, namespace)  # Test-owned literals, never a scanned project.
    assert namespace['execute'](**inputs) == {'status': expected, 'source_unchanged': False}
    success = analyze_inputs(source, 'execute', inputs, success={'field': 'status', 'expected': 'ready'})
    flag = analyze_inputs(source, 'execute', inputs, success={'field': 'source_unchanged', 'expected': True})
    assert success['status'] == ('holds_in_model' if expected == 'ready' else 'counterexample_in_model')
    assert flag['status'] == 'counterexample_in_model' and flag['outcome'] == 'normal_return'
