"""Local worker transport tests; actual Windows ACL evidence is a separate pilot."""
import sys
import time

import pytest

from runtime.remote_support_exchange import work_once, validate_execution, validate_location
from runtime.remote_support_protocol import load, save
from runtime.remote_support_release import inventory


@pytest.fixture
def ticket(tmp_path):
    area = tmp_path / 'exchange'
    folder = area / ('a'*32)
    source = folder / 'source'
    source.mkdir(parents=True)
    (folder / 'output').mkdir()
    (source / 'check.py').write_text('print("completed-once")\n')
    request = {'schema':'cos.local_worker.v1',
        'command':{'argv':[sys.executable,'-B','check.py'],'timeout':5},
        'context':{'phase':'resume'},'expected':inventory(source,['check.py']),
        'expires_at':time.time()+30}
    save(folder/'request.json',request)
    return area, folder, request


def test_worker_executes_once_and_returns_bound_result(ticket):
    area, folder, request = ticket
    result = work_once(area)
    assert result[0]['passed']
    receipt = (folder/'output/completed.json').read_bytes()
    assert load(folder/'output/completed.json')['result']['output'].strip() == 'completed-once'
    assert work_once(area) == []
    assert (folder/'output/completed.json').read_bytes() == receipt


def test_claim_left_by_crash_is_never_reexecuted(ticket):
    area, folder, _ = ticket
    (folder/'output/claim.json').write_text('interrupted')
    assert work_once(area) == []
    assert not (folder/'output/completed.json').exists()


def test_expired_ticket_never_runs(ticket):
    area, folder, request = ticket
    request['expires_at'] = time.time()-1
    save(folder/'request.json',request)
    assert work_once(area) == []
    assert not (folder/'output/claim.json').exists()


def test_recursive_dispatch_is_rejected(ticket):
    area, folder, request = ticket
    request['context']['execution'] = {'nested':True}
    save(folder/'request.json',request)
    result = work_once(area)
    assert result[0]['reason'] == 'support_nested_worker_forbidden'
    assert not (folder/'output/completed.json').exists()
    assert work_once(area) == []


@pytest.mark.parametrize('change',['same_identity','relative','extra','sid'])
def test_invalid_execution_policy_rejected(tmp_path, change):
    policy = {'kind':'windows_file_worker.v1','root':str(tmp_path),
              'controller_sid':'S-1-5-21-1001','worker_sid':'S-1-5-21-1009'}
    if change == 'same_identity':
        policy['worker_sid'] = policy['controller_sid']
    elif change == 'relative':
        policy['root'] = 'relative'
    elif change == 'extra':
        policy['shell'] = True
    else:
        policy['worker_sid'] = 'Everyone & command'
    with pytest.raises(ValueError):
        validate_execution(policy)


@pytest.mark.parametrize('relative',['.','child'])
def test_exchange_cannot_expose_private_tree(tmp_path,relative):
    private = tmp_path/'private'
    with pytest.raises(ValueError,match='must_be_separate'):
        validate_location({'root':str(private/relative)},private)
    with pytest.raises(ValueError,match='must_be_separate'):
        validate_location({'root':str(tmp_path)},private)
