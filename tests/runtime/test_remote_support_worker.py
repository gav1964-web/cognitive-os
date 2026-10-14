"""Worker outcome and inference usage survive subprocess/message boundaries."""
import json
import sys

import pytest

from runtime.remote_support_protocol import load, save
from runtime.remote_support_release import inventory, run_check
from tests.runtime.test_remote_support import setup_support, response


@pytest.mark.parametrize('passed,exitcode,expected', [(True, 0, True), (False, 0, False), (True, 1, False)])
def test_worker_result_is_required_to_agree_with_process(tmp_path, passed, exitcode, expected):
    source = tmp_path / 'source'
    source.mkdir()
    body = {'passed': passed, 'usage': {'reported': 123, 'unknown_reserved': 0}}
    (source / 'check.py').write_text(
        'import os,json,sys\nfrom pathlib import Path\n'
        f'Path(os.environ["COS_SUPPORT_RESULT"]).write_text(json.dumps({body!r}))\n'
        f'sys.exit({exitcode})\n')
    result = run_check(source, {'argv': [sys.executable, 'check.py'], 'timeout': 10},
                       tmp_path / 'out.log', inventory(source, ['check.py']), 10, {'phase': 'resume'})
    assert result['passed'] is expected
    assert result['worker_result'] == body


def test_usage_survives_failed_resume_and_duplicate_message(setup_support, monkeypatch):
    supervisor, incident, _, _ = setup_support()
    import runtime.remote_support_supervisor as module
    original = module.run_check

    def run(*args):
        result = original(*args)
        if args[-1]['phase'] == 'resume':
            assert args[-1]['budget']['remaining_tokens'] == 9170
            result.update(passed=False, worker_result={'passed': False,
                'usage': {'reported': 321, 'unknown_reserved': 456}})
        return result

    monkeypatch.setattr(module, 'run_check', run)
    message = response(incident)
    reply = supervisor.receive(message)
    assert reply['payload']['reason'] == 'support_resume_failed'
    assert reply['payload']['usage']['reported'] == 1121
    assert reply['payload']['usage']['unknown_reserved'] == 486
    before = load(supervisor.home / 'state.json')
    assert supervisor.receive(message) == reply
    assert load(supervisor.home / 'state.json') == before


def test_worker_over_budget_cannot_complete(setup_support, monkeypatch):
    supervisor, incident, _, _ = setup_support()
    import runtime.remote_support_supervisor as module
    original = module.run_check

    def run(*args):
        result = original(*args)
        if args[-1]['phase'] == 'resume':
            result['worker_result'] = {'passed': True,
                'usage': {'reported': 10000, 'unknown_reserved': 0}}
        return result

    monkeypatch.setattr(module, 'run_check', run)
    reply = supervisor.receive(response(incident))
    assert reply['payload']['status'] != 'completed'
    assert reply['payload']['checks']['1-resume']['budget_exceeded']
    assert reply['payload']['active']['release'] == 'baseline'
