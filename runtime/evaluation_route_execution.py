"""Common task15 verification and metered gateway transport for route trials."""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .local_inference import LocalInferenceError, call_json_chat


class RouteBudgetExceeded(RuntimeError):
    pass


class MeteredChat:
    def __init__(self, config, *, max_calls=20, timeout=900, max_tokens=120000):
        self.records, self.calls, self.token_bound, self.accounted_tokens = [], 0, 0, 0
        self.started = time.monotonic()
        self.max_calls, self.timeout, self.max_tokens = max_calls, timeout, max_tokens
        self.config = dataclasses.replace(config, telemetry_sink=self.records.append,
                                          max_output_tokens=3000)

    def __call__(self, messages):
        remaining = self.timeout - (time.monotonic() - self.started)
        # Conservative UTF-8 byte reservation, not a provider tokenizer measurement.
        reservation = len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 3000
        attempts = sum(r.get('event') != 'route_skipped' for r in self.records)
        if self.calls >= self.max_calls or attempts >= self.max_calls or remaining <= 0 or self.accounted_tokens + reservation > self.max_tokens:
            raise RouteBudgetExceeded('call_time_or_conservative_token_budget')
        self.calls += 1
        self.token_bound += reservation
        previous = len(self.records)
        try:
            return call_json_chat(messages, config=dataclasses.replace(self.config,
                fallbacks=self.config.fallbacks[:max(0, self.max_calls - attempts - 1)],
                timeout_seconds=min(self.config.timeout_seconds, remaining)))
        except LocalInferenceError as exc:
            if not any(r.get('event') == 'attempt_failed' for r in self.records[previous:]):
                self.records.append({'event': 'attempt_failed',
                    'requested_model': self.config.model, 'provider_label': self.config.provider_label,
                    'http_status': getattr(exc, 'http_status', None),
                    'error_type': type(exc).__name__,
                    'response_observed': any(r.get('event', 'response') == 'response'
                                             for r in self.records[previous:])})
            raise
        finally:
            responses = [r for r in self.records[previous:] if r.get('event', 'response') == 'response']
            if responses and all(type(r.get('total_tokens')) is int and r['total_tokens'] > 0 for r in responses):
                self.accounted_tokens += sum(r['total_tokens'] for r in responses)
            else:
                self.accounted_tokens += reservation

    def usage(self):
        responses = [r for r in self.records if r.get('event', 'response') == 'response']
        known = bool(responses) and all(r.get('usage_reported') and
            type(r.get('prompt_tokens')) is int and type(r.get('completion_tokens')) is int and
            r['prompt_tokens'] + r['completion_tokens'] > 0 for r in responses)
        return {'status': 'reported' if known else 'unknown',
                'input': sum(r['prompt_tokens'] for r in responses) if known else None,
                'output': sum(r['completion_tokens'] for r in responses) if known else None,
                'conservative_reserved_tokens': self.token_bound,
                'accounted_tokens': self.accounted_tokens,
                'calls': self.calls, 'estimated_cost': None}


def verify_task15(project: Path, control: Path) -> dict:
    from evaluation.acceptance.check_uppercase_cli import check_project
    control.mkdir(parents=True, exist_ok=True)
    (control / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    junit = control / 'pytest.xml'
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL'}}
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    args = ['.', '-q', '--tb=short', '-c', str(control / 'pytest.ini'),
            '--rootdir=' + str(project), '--confcutdir=' + str(project),
            '--basetemp=' + str(control / 'tmp'), '--junitxml=' + str(junit)]
    bootstrap = ('import sys,json; from pathlib import Path; '
                 'sys.path[:0]=[sys.argv[1],str(Path(sys.argv[1])/"src")]; '
                 'import pytest; raise SystemExit(pytest.main(json.loads(sys.argv[2])))')
    try:
        run = subprocess.run([sys.executable, '-I', '-c', bootstrap, str(project), json.dumps(args)],
                             cwd=project, env=env, capture_output=True, timeout=60)
        log = (run.stdout + run.stderr).decode('utf-8', errors='replace')
        code = run.returncode
    except subprocess.TimeoutExpired:
        log, code = 'verification_timeout', 124
    (control / 'pytest.log').write_text(log, encoding='utf-8')
    passing = 0
    if junit.exists():
        try:
            passing = sum(not any(c.find(t) is not None for t in ('failure', 'error', 'skipped'))
                          for c in ET.parse(junit).iter('testcase'))
        except ET.ParseError:
            pass
    acceptance = check_project(project)
    return {'status': 'passed' if code == 0 and passing > 0 and acceptance['status'] == 'passed' else 'failed',
            'pytest': {'returncode': code, 'passing': passing, 'log_tail': log[-5000:]},
            'acceptance': acceptance,
            'boundary': 'local subprocess, limited environment; not an OS security sandbox'}
