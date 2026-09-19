"""Discovery must not execute project code unbounded inside the controller."""
import json
import sys
from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_environment import environment_harness_summary

ROOT = Path(__file__).resolve().parents[2]


def test_hanging_discovery_becomes_structured_timeout(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'slow.py').write_text('def normalize(value: str) -> str:\n    while True:\n        pass\n')
    obligations = tmp_path / 'obligations.json'
    obligations.write_text(json.dumps([{
        'target': 'slow.py:normalize', 'kind': 'positive_contract_case',
        'given': {'value': 'sample'}, 'expect': {'result': 'string'},
    }]))
    result = environment_harness_summary(
        root=ROOT, project_dir=project, obligations_path=obligations,
        python_executable=Path(sys.executable), timeout_seconds=1,
    )
    assert result['environment_probe']['status'] == 'timed_out'
    assert result['callable_harness_count'] == 0


def test_host_probe_failure_cannot_become_structural_success(tmp_path, monkeypatch):
    observed = {}
    def failed_probe(**kwargs):
        observed['python'] = kwargs['python_executable']
        return {
            'callable_harness_count': 0, 'signal_strength': 'environment_probe_failed',
            'skipped_reason_counts': {'environment_harness_probe_failed': 1}, 'skipped_targets': [],
            'environment_probe': {'status': 'timed_out', 'returncode': 124},
        }
    def unexpected_run(**kwargs):
        raise AssertionError('failed discovery must not execute structural fallback')
    monkeypatch.setattr('runtime.executable_acceptance.environment_harness_summary', failed_probe)
    monkeypatch.setattr('runtime.executable_acceptance.run_acceptance_command', unexpected_run)
    result = run_executable_acceptance(
        root=ROOT, project_dir=tmp_path, test_plan={'executable_acceptance': {'obligations': []}},
        work_dir=tmp_path / 'execution',
    )
    assert result['status'] == 'failed'
    assert result['command']['returncode'] == 124
    assert observed['python'] == Path(sys.executable)
