"""Executable pickle round-trip oracle rendered as a standalone pytest module.

Sample descriptors use the competency's existing `__sample__` notation; helper
classes live at module level so that the samples themselves remain picklable.
"""
from __future__ import annotations

from typing import Any

SAMPLE_KINDS = {'named_object', 'method_object', 'format_object', 'response', 'excinfo', 'bytes',
                'cooldown', 'path', 'exception', 'os_error', 'called_process_error'}

_HELPERS = '''

class _MethodObject:
    def __init__(self, methods):
        self._methods = methods

    def __getattr__(self, name):
        if name.startswith('__') or name not in self._methods:
            raise AttributeError(name)
        value = self._methods[name]
        return lambda *a, **k: value


class _FormatObject:
    def __init__(self, text):
        self._text = text

    def format(self, *args, **kwargs):
        return self._text

    def __str__(self):
        return self._text


class _Response:
    def __init__(self, payload):
        self.status_code = payload['status_code']
        self.url = payload['url']
        self.content = payload['content'].encode('utf-8')
        self.text = payload['text']
        self._json = payload['json']

    def json(self):
        return self._json


def _val(v):
    if isinstance(v, list):
        return [_val(item) for item in v]
    if isinstance(v, tuple):
        return tuple(_val(item) for item in v)
    if not isinstance(v, dict) or '__sample__' not in v:
        return v
    kind = v['__sample__']
    if kind == 'named_object':
        return types.SimpleNamespace(**{k: _val(x) for k, x in v.items() if k != '__sample__'})
    if kind == 'excinfo':
        return types.SimpleNamespace(formatted=v['formatted'], type=RuntimeError, msg=v['msg'], errdisplay=v['errdisplay'])
    if kind == 'method_object':
        return _MethodObject(v['methods'])
    if kind == 'response':
        return _Response(v)
    if kind == 'bytes':
        return v['value'].encode('utf-8')
    if kind == 'format_object':
        return _FormatObject(v['value'])
    if kind == 'cooldown':
        return types.SimpleNamespace(rate=v['rate'], per=v['per'])
    if kind == 'path':
        return pathlib.Path(v['value'])
    if kind == 'exception':
        return RuntimeError(v['message'])
    if kind == 'os_error':
        return OSError(v['errno'], v['message'])
    if kind == 'called_process_error':
        return subprocess.CalledProcessError(v['returncode'], v['cmd'], output=v['stdout'], stderr=v['stderr'])
    raise ValueError(kind)


def _same(a, b):
    if type(a) is not type(b):
        return False
    try:
        if a == b:
            return True
    except Exception:
        pass
    if isinstance(a, BaseException):
        return _same(a.args, b.args) and _same(vars(a), vars(b))
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if hasattr(a, '__dict__'):
        return _same(vars(a), vars(b))
    return False
'''


def supported_sample(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, (list, tuple)):
        return all(supported_sample(v) for v in value)
    if isinstance(value, dict):
        if '__sample__' in value and value['__sample__'] not in SAMPLE_KINDS:
            return False
        return all(isinstance(k, str) and supported_sample(v) for k, v in value.items())
    return False


def render_test(*, module: str, import_root: str, class_name: str, test_name: str,
                args: list, kwargs: dict) -> str:
    path_setup = ''
    if import_root:
        depth = 1  # generated tests live directly under tests/
        path_setup = (f"sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[{depth}] / {import_root!r}))\n")
    return (
        'import pathlib\nimport pickle\nimport subprocess\nimport sys\nimport types\n\n'
        + path_setup
        + f'from {module} import {class_name}  # noqa: E402\n'
        + _HELPERS
        + f'\n\ndef {test_name}():\n'
        f'    before = {class_name}(*_val({args!r}), **{{k: _val(x) for k, x in {kwargs!r}.items()}})\n'
        '    try:\n'
        '        after = pickle.loads(pickle.dumps(before))\n'
        '    except Exception as exc:\n'
        "        raise AssertionError(f'pickle round trip failed: {exc!r}') from exc\n"
        '    assert type(after) is type(before)\n'
        '    assert _same(after.args, before.args)\n'
        '    assert _same(vars(after), vars(before))\n'
    )
