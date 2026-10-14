"""Replay trusted tests in source copies; this subprocess is not an OS sandbox."""
from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from cognitive_replay.process import isolated_environment, run_command


def verify_snapshot(project: Path, control: Path, *, test_targets: list[str],
                    timeout: int = 180, pytest_plugins: list[str] | None = None) -> dict:
    control.mkdir(parents=True, exist_ok=False)
    if not test_targets:
        return {'status': 'blocked', 'reason': 'explicit_regression_scope_required'}
    for target in test_targets:
        path = project / target
        if (target.startswith('-') or '::' in target or Path(target).is_absolute()
                or not path.resolve().is_relative_to(project.resolve()) or not path.exists()):
            return {'status': 'blocked', 'reason': 'invalid_regression_scope'}
    junit = control / 'pytest.xml'
    bootstrap = (
        'import sys,json; from pathlib import Path; p=Path(sys.argv[1]); '
        'sys.path[:0]=[str(p),str(p/"src")]+[str(v) for v in (p/"packages").glob("*/src")]; '
        'import pytest; raise SystemExit(pytest.main(json.loads(sys.argv[2])))'
    )
    config = next((project / name for name in ('pytest.ini', '.pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg')
                   if (project / name).is_file()), control / 'pytest.ini')
    if config.parent == control:
        config.write_text('[pytest]\n', encoding='utf-8')
    arguments = [*test_targets, '-q', '--import-mode=importlib', '-c', str(config), f'--rootdir={project}',
                 f'--basetemp={control / "tmp"}', f'--junitxml={junit}']
    for plugin in pytest_plugins or []:
        arguments.extend(['-p', plugin])
    env = isolated_environment(control / 'environment', Path(sys.executable))
    result = run_command([sys.executable, '-I', '-c', bootstrap, str(project), json.dumps(arguments)],
                         cwd=project, timeout=timeout, env=env)
    (control / 'stdout.txt').write_text(result['stdout'], encoding='utf-8')
    (control / 'stderr.txt').write_text(result['stderr'], encoding='utf-8')
    cases, passing = [], 0
    if junit.is_file():
        try:
            for case in ET.parse(junit).iter('testcase'):
                cases.append((case.get('classname', ''), case.get('name', '')))
                passing += not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
        except ET.ParseError:
            return {'status': 'failed', 'reason': 'invalid_junit'}
    checks = []
    # Existing repository boundary checker remains authoritative when available.
    if (project / 'tools/project_context.py').is_file() and (project / 'docs/architecture/subsystems.json').is_file():
        boundary = run_command([sys.executable, 'tools/project_context.py', '--check'],
                               cwd=project, timeout=timeout, env=env)
        checks.append({'name': 'project_boundaries', 'returncode': boundary['returncode']})
        (control / 'boundaries.txt').write_text(boundary['stdout'] + boundary['stderr'], encoding='utf-8')
    good = result['returncode'] == 0 and passing > 0 and all(c['returncode'] == 0 for c in checks)
    return {'status': 'passed' if good else 'failed', 'returncode': result['returncode'],
            'test_targets': test_targets, 'collected': sorted(cases), 'passing': passing,
            'checks': checks, 'junit': str(junit), 'log_directory': str(control),
            'reason': None if good else 'regression_or_boundary_check_failed'}
