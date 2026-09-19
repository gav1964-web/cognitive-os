"""Predeclared task15 acceptance; independent of generated project tests."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def check_project(project: Path) -> dict:
    project = project.resolve()
    checks = []
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL',
    }}
    env['PYTHONUTF8'] = '1'
    with tempfile.TemporaryDirectory(prefix='uppercase-acceptance-') as temporary:
        folder = Path(temporary)
        for name, data, expected in [
            ('unicode', 'Hello, мир!\nStraße\n'.encode(), 'HELLO, МИР!\nSTRASSE\n'.encode()),
            ('empty', b'', b''), ('crlf', b'a\r\nb\r\n', b'A\r\nB\r\n'),
            ('invalid_utf8', b'\xff', None), ('missing', None, None),
            ('same_path', b'unchanged', None),
        ]:
            source, output = folder / (name + '.in'), folder / (name + '.out')
            if data is not None:
                source.write_bytes(data)
            if name == 'same_path':
                output = source
            else:
                output.write_bytes(b'existing output')
            before = output.read_bytes()
            try:
                process = subprocess.run([sys.executable, str(project / 'main.py'), str(source), str(output)],
                                         cwd=project, env=env, capture_output=True, timeout=10)
                preserved = (source.read_bytes() == data) if data is not None else not source.exists()
                passed = preserved and (process.returncode == 0 and output.read_bytes() == expected
                                        if expected is not None else process.returncode != 0 and output.read_bytes() == before)
                check = {'id': name, 'passed': passed, 'returncode': process.returncode}
                if not passed and expected is not None:
                    check['expected_hex'] = expected.hex()
                    check['observed_hex'] = output.read_bytes()[:256].hex() if output.is_file() else None
                checks.append(check)
            except (OSError, subprocess.TimeoutExpired):
                checks.append({'id': name, 'passed': False, 'reason': 'execution_failed_or_timed_out'})
    return {'status': 'passed' if all(c['passed'] for c in checks) else 'failed',
            'checks': checks, 'scope': 'Six frozen CLI behavior cases; no model or comparative quality claim.'}
