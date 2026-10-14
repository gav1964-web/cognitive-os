"""An actual intake signature must survive the independent acceptance runner."""
import sys
import pytest
from pathlib import Path

from runtime.native_failure_acceptance import build_native_acceptance, run_native_acceptance
from runtime.project_development_policy import load_project_development_policy
from runtime.project_failure_evidence_packet import build_failure_evidence_packet
from runtime.project_native_failure_intake import run_project_native_failure_intake
from runtime.stage_finalization_workspace import inventory, snapshot


@pytest.mark.parametrize('custom_plugin', [False, True])
def test_color_config_and_assertion_diagnostics_keep_intake_identity(tmp_path, custom_plugin):
    project = tmp_path / 'project'
    (project / 'tests').mkdir(parents=True)
    source = 'def format_zero(value):\n    return "0/1" if value == 0 else str(value)\n'
    (project / 'logic.py').write_text(source)
    (project / 'pytest.ini').write_text('[pytest]\naddopts = --color=yes\n')
    plugins = ['env_plugin'] if custom_plugin else []
    if custom_plugin:
        (project/'env_plugin.py').write_text('def pytest_addoption(parser):\n    parser.addoption("--native-environment-flag", action="store_true")\n')
        (project/'pytest.ini').write_text('[pytest]\naddopts = --color=yes --native-environment-flag\n')
    (project / 'tests/test_logic.py').write_text(
        'from logic import format_zero\ndef test_zero():\n    assert format_zero(0) == "0"\n')
    policy = load_project_development_policy()
    policy['native_failure_intake'].update(local_editable_install=False,
        python_executable=sys.executable, nested_pytest_plugins=plugins, timeout_seconds=15,
        shard_on_timeout=False)
    if custom_plugin:
        policy['native_failure_intake']['pytest_arguments'].extend(['-p', 'env_plugin'])
    intake = run_project_native_failure_intake(root=tmp_path, projects=[project],
        project_stratum='library_pure_transform', test_targets=['tests/test_logic.py'], policy=policy)
    case = intake['cases'][0]
    assert case['status'] == 'qualified_failure', case
    request = case['change_request']
    packet = build_failure_evidence_packet(project_dir=project,
        failure=request['contract_failure_evidence'][0], chain_case=case,
        native_replay_settings={'pytest_plugins': plugins, 'timeout_seconds':20})
    assert packet['status'] == 'complete'
    contract = build_native_acceptance({'contract_mode': 'failure_repair',
        'implementation_delta': {'intent': {'failure_evidence_packet': packet}},
        'acceptance_criteria': [{'id': 'AC-FAILURE-REPLAY-ZERO'}]}, request['target'])
    assert contract['pytest_plugins'] == plugins
    patched = tmp_path / 'patched'
    snapshot(project, patched, inventory(project))
    (patched / 'logic.py').write_text(source.replace('"0/1"', '"0"'))
    result = run_native_acceptance(source_project=project, patched_project=patched,
        contract=contract, work_dir=tmp_path / 'acceptance')
    assert result['status'] == 'passed', (result['reason'], result['summary'], result['probes'])
    assert result['summary']['native_replay_checks']['recorded_failure_reproduced']
    for probe in result['probes'][:2]:
        assert '\x1b' not in Path(probe['output']).read_text(encoding='utf-8')
        assert probe['intake_signature'] == request['failure_signature']


def test_object_addresses_are_volatile_but_values_and_types_are_not():
    from runtime.project_native_failure_binding import _stable_summary
    first = "assert 'localhost' is <object object at 0x1234>"
    second = "assert 'localhost' is <object object at 0xabcd>"
    assert _stable_summary(first) == _stable_summary(second)
    assert _stable_summary(first) != _stable_summary(first.replace('localhost', 'remote'))
    assert _stable_summary(first) != _stable_summary(first.replace('<object', '<Custom'))
    assert _stable_summary("assert '0x1234' == '0xabcd'") == "assert '0x1234' == '0xabcd'"


def test_rewritten_assertion_identity_uses_values_and_ignores_warning_count(tmp_path):
    from runtime.project_native_failure_binding import _interpret_pytest_result
    output = ('E       assert False is True\n'
        'FAILED tests/test_logic.py::test_false - assert False is True\n1 failed in 0.28s\n')
    plain = _interpret_pytest_result(tmp_path, 1, output, {})
    warned = _interpret_pytest_result(tmp_path, 1, output.replace('1 failed in', '1 failed, 2 warnings in'), {})
    other = _interpret_pytest_result(tmp_path, 1, output.replace('False is True', 'None is True'), {})
    named = _interpret_pytest_result(tmp_path, 1, output.replace('E       assert', 'E AssertionError: assert'), {})
    assert plain['failure_summary'] == 'AssertionError: assert False is True'
    assert plain['failure_signature'] == warned['failure_signature'] == named['failure_signature']
    assert plain['failure_signature'] != other['failure_signature']
