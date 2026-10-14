"""Incomplete subprocess reports cannot become passing or counterexample evidence."""
import json
from pathlib import Path
import sys

import pytest

from runtime.native_failure_acceptance import _probe


@pytest.mark.parametrize('exit_code', [0, 1, 124])
@pytest.mark.parametrize('report', [None, '', '<testsuite><testcase',
                                    '<testsuite><testcase name="partial"/></testsuite>'])
def test_incomplete_probe_preserves_exit_and_fails_closed(tmp_path, monkeypatch, exit_code, report):
    project = tmp_path / 'project'
    project.mkdir()
    control = tmp_path / 'control'
    def run(command, **kwargs):
        if report is not None:
            (control / 'pytest.xml').write_text(report, encoding='utf-8')
        return {'returncode': exit_code, 'stdout': 'partial output', 'stderr': ''}
    monkeypatch.setattr('runtime.native_failure_acceptance.run_command', run)
    result = _probe(project, control, ['test_case.py::test_case'], [], 1, Path(sys.executable))
    valid = report is not None and report.endswith('</testsuite>')
    if not valid or exit_code == 124:
        assert result['returncode'] not in (0, 1)
        assert result['passing'] == 0 and result['collected'] == []
        assert result['intake_signature'] is None
        if exit_code == 124:
            assert result['reason'] == 'native_probe_timeout'
    receipt = json.loads((control / 'process.json').read_text())
    assert receipt['returncode'] == exit_code
    assert receipt['timed_out'] == (exit_code == 124)
