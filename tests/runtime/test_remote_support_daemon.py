"""Lifecycle and deployment regressions; no SCM mutation or paid model calls."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from runtime import remote_support_daemon as daemon
from runtime.remote_support_deployment import service_sid, verify_bundle
from runtime.remote_support_exchange import work_once
from runtime.remote_support_protocol import digest, load, save
from runtime.remote_support_release import inventory, run_check


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    for name in ('exchange', 'state'):
        (tmp_path/name).mkdir()
    config = {'schema':'cos.worker_service.v1', 'worker_sid':'S-1-5-21-1009',
              'controller_sid':'S-1-5-21-1001', 'exchange':str(tmp_path/'exchange'),
              'state':str(tmp_path/'state'), 'poll_seconds':0.1}
    save(tmp_path/'worker.json', config)
    monkeypatch.setattr(daemon, 'current_sid', lambda: config['worker_sid'])
    return tmp_path/'worker.json', config


def ticket(area, name, source='print("ok")'):
    folder = area/name
    (folder/'source').mkdir(parents=True)
    (folder/'output').mkdir()
    (folder/'source/check.py').write_text(source)
    save(folder/'request.json', {'schema':'cos.local_worker.v1',
        'command':{'argv':[sys.executable, '-B', 'check.py'], 'timeout':10},
        'context':{}, 'expected':inventory(folder/'source', ['check.py']),
        'expires_at':time.time()+30})
    return folder


def test_poisoned_ticket_does_not_starve_valid_job(tmp_path):
    bad = ticket(tmp_path, 'a'*32)
    (bad/'request.json').write_text('{broken')
    good = ticket(tmp_path, 'b'*32)
    rows = work_once(tmp_path)
    assert rows[0]['status'] == 'rejected'
    assert rows[1]['passed'] is True
    assert not (bad/'output/claim.json').exists()
    assert load(good/'output/completed.json')['result']['passed']


def test_stopping_does_not_claim_next_job(tmp_path):
    folder = ticket(tmp_path, 'a'*32)
    assert work_once(tmp_path, stop_requested=lambda: True) == []
    assert not (folder/'output/claim.json').exists()


def test_stop_terminates_active_child_and_retains_claim(tmp_path):
    folder = ticket(tmp_path, 'a'*32, 'import time; print("started", flush=True); time.sleep(60)')
    stop = threading.Event()
    timer = threading.Timer(1, stop.set)
    timer.start()
    try:
        start = time.monotonic()
        rows = work_once(tmp_path, stop_requested=stop.is_set)
    finally:
        timer.cancel()
    assert time.monotonic()-start < 15
    assert not rows[0]['passed']
    result = load(folder/'output/completed.json')['result']
    assert result['cancelled'] and not result['timed_out']
    assert result['returncode'] is not None
    assert work_once(tmp_path) == []


def test_stop_before_launch_does_not_spawn(tmp_path):
    with pytest.raises(ValueError, match='stopping'):
        run_check(tmp_path, {'argv':['invalid-command'], 'timeout':1}, tmp_path/'x.log',
                  {}, 1, {}, stop_requested=lambda: True)
    assert not (tmp_path/'x.log').exists()


def test_os_lock_excludes_second_process_and_releases_after_exit(tmp_path):
    script = ('from runtime.remote_support_daemon import single_instance; '
              'from pathlib import Path; import sys; '
              'ctx=single_instance(Path(sys.argv[1])); ctx.__enter__()')
    with daemon.single_instance(tmp_path):
        result = subprocess.run([sys.executable, '-B', '-c', script, str(tmp_path)],
                                capture_output=True, timeout=10)
        assert result.returncode != 0
        assert b'support_service_already_running' in result.stderr
    result = subprocess.run([sys.executable, '-B', '-c', script, str(tmp_path)],
                            capture_output=True, timeout=10)
    assert result.returncode == 0
    with daemon.single_instance(tmp_path):
        pass


def test_daemon_identity_failure_precedes_claim(deployment, monkeypatch):
    path, config = deployment
    folder = ticket(Path(config['exchange']), 'a'*32)
    monkeypatch.setattr(daemon, 'current_sid', lambda: 'S-1-5-21-9999')
    with pytest.raises(ValueError, match='identity_mismatch'):
        daemon.serve(path, threading.Event())
    assert not (folder/'output/claim.json').exists()


def test_daemon_processes_ticket_and_stops_cleanly(deployment):
    path, config = deployment
    folder = ticket(Path(config['exchange']), 'a'*32)
    stop = threading.Event()
    timer = threading.Timer(1, stop.set)
    timer.start()
    try:
        daemon.serve(path, stop)
    finally:
        timer.cancel()
    assert load(folder/'output/completed.json')['result']['passed']
    assert load(Path(config['state'])/'status.json')['phase'] == 'stopped'
    assert work_once(config['exchange']) == []


@pytest.mark.parametrize('change', ['identity', 'layout', 'poll', 'extra'])
def test_config_rejects_invalid_deployment(deployment, change):
    path, config = deployment
    if change == 'identity':
        config['worker_sid'] = config['controller_sid']
    elif change == 'layout':
        config['exchange'] = config['state']
    elif change == 'poll':
        config['poll_seconds'] = float('inf')
    else:
        config['key_file'] = 'secret'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        daemon.read_config(path)


def test_service_sid_matches_windows_sc_result():
    assert service_sid() == 'S-1-5-80-2270994135-4294812135-2025563444-196573808-166997021'


@pytest.mark.skipif(os.name != 'nt', reason='Windows installer')
def test_install_without_admin_fails_before_reading_or_mutating_bundle(tmp_path, monkeypatch):
    import ctypes
    from runtime.remote_support_deployment import install
    monkeypatch.setattr(ctypes.windll.shell32, 'IsUserAnAdmin', lambda: False)
    with pytest.raises(PermissionError, match='requires_windows_administrator'):
        install(tmp_path/'does-not-exist', 'S-1-5-21-1001')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('change', ['none', 'hash', 'extra', 'escape'])
def test_bundle_verification(tmp_path, change):
    (tmp_path/'payload.py').write_text('pass')
    manifest = {'schema':'cos.worker_bundle.v1', 'files':{'payload.py':digest(b'pass')}}
    if change == 'hash':
        (tmp_path/'payload.py').write_text('changed')
    elif change == 'extra':
        (tmp_path/'surprise.pth').write_text('import arbitrary_code')
    elif change == 'escape':
        manifest['files']['../escape'] = digest(b'')
    save(tmp_path/'manifest.json', manifest)
    if change == 'none':
        assert verify_bundle(tmp_path) == manifest
    else:
        with pytest.raises(ValueError):
            verify_bundle(tmp_path)


@pytest.mark.skipif(os.name != 'nt', reason='Windows service process containment')
def test_service_death_kills_child_tree(tmp_path):
    pytest.importorskip('win32job')
    child_pid = tmp_path/'child.pid'
    script = ('from tools.remote_support_service import contain_process_tree; '
              'import subprocess,sys,time; from pathlib import Path; contain_process_tree(); '
              'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
              'Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)')
    parent = subprocess.Popen([sys.executable, '-B', '-c', script, str(child_pid)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    child_handle = None
    try:
        until = time.monotonic()+10
        while not child_pid.exists() and time.monotonic() < until and parent.poll() is None:
            time.sleep(0.05)
        assert child_pid.exists(), parent.stderr.read() if parent.poll() is not None else 'startup timeout'
        import win32api
        import win32event
        child_handle = win32api.OpenProcess(0x00100000, False, int(child_pid.read_text()))
        parent.kill()
        parent.wait(timeout=10)
        assert win32event.WaitForSingleObject(child_handle, 5000) == win32event.WAIT_OBJECT_0
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=10)
        if child_handle:
            child_handle.Close()
        parent.stderr.close()
