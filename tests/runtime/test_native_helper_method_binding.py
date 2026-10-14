"""A transparent wrapper binds an observed API without asserting a defect location."""
import pytest

from runtime.project_native_failure_target_binding import _test_assertion_causal_analysis
from runtime.project_native_failure_helper_binding import helper_method_binding
from runtime.project_failure_evidence_packet import _helper_provenance
from runtime.project_native_failure_pytest import _run_pytest
from tests.runtime.test_native_relative_test_imports import write


def workspace(root, *, helper=None, production=None):
    write(root, 'tests/__init__.py', '')
    write(root, 'core.py', production or 'class Worker:\n    def convert(self, value): return value\n')
    write(root, 'tests/utils.py', helper or 'from core import Worker\ndef render(value, **options):\n'
          '    options = {"strip": None, **options}\n    return Worker(**options).convert(value)\n')
    write(root, 'tests/test_case.py', 'from .utils import render\ndef test_case(): assert render("x") == "y"\n')
    return _test_assertion_causal_analysis(root, ['tests/test_case.py::test_case'])


def test_transparent_wrapper_is_observed_api_not_root_cause(tmp_path):
    result = workspace(tmp_path)
    assert result['production_targets'] == ['core.py:Worker.convert']
    proof, = result['helper_bindings']
    assert proof['authority'] == 'observed_api_only_not_root_cause'
    assert proof['constructor_defaults'] == {'strip': None}
    assert proof['helper']['path'] == 'tests/utils.py'
    assert len(proof['helper']['file_sha256']) == len(proof['target_file_sha256']) == 64
    assert 'return value' in proof['method_source']


@pytest.mark.parametrize('body', [
    'return Worker().convert(value.strip())',
    'return Worker().convert(value).strip()',
    'return Worker().convert(value) + "suffix"',
    'value = value.strip()\n    return Worker().convert(value)',
    'if value:\n        return Worker().convert(value)\n    return Other().convert(value)',
    'return Worker().convert("constant")',
    'worker = Worker()\n    worker.convert = lambda v: v\n    return worker.convert(value)',
])
def test_opaque_helper_does_not_bind(tmp_path, body):
    result = workspace(tmp_path, helper='from core import Worker\ndef render(value):\n    ' + body + '\n')
    assert not result['production_targets']
    assert result['helper_bindings'][0]['status'] == 'unbound'


@pytest.mark.parametrize('production', [
    'class Base:\n    def convert(self, value): return value\nclass Worker(Base):\n    pass\n',
    'class Worker:\n    def __getattribute__(self, name): return lambda v: v\n    def convert(self, value): return value\n',
    'class Worker:\n    def __new__(cls): return object()\n    def convert(self, value): return value\n',
    'class Worker:\n    @property\n    def convert(self): return lambda v: v\n',
    'class Worker:\n    def convert(self, value): return value\n    convert = lambda self, value: value\n',
    'class Worker:\n    def convert(self, value): return value\nWorker.convert = lambda self, value: value\n',
    'class Worker:\n    def convert(self, value): return value\nsetattr(Worker, "convert", lambda self, v: v)\n',
    'class Worker:\n    def convert(self, value): return value\nWorker = something_else\n',
])
def test_overrides_and_dynamic_dispatch_do_not_bind(tmp_path, production):
    assert not workspace(tmp_path, production=production)['production_targets']


def test_reversed_defaults_do_not_override_supplied_input(tmp_path):
    result = workspace(tmp_path, helper='from core import Worker\ndef render(value, **options):\n'
                       '    options = {**options, "strip": None}\n    return Worker(**options).convert(value)\n')
    assert not result['production_targets']
    assert 'preserve_supplied_options' in result['helper_bindings'][0]['reason']


def test_changed_helper_source_invalidates_old_binding(tmp_path):
    result = workspace(tmp_path)
    source = result['test_support_sources'][0]
    write(tmp_path, 'tests/utils.py', 'from core import Worker\ndef render(value): return "changed"\n')
    assert helper_method_binding(tmp_path, source)['status'] == 'unbound'


def test_packet_rechecks_helper_and_owned_method_hashes(tmp_path):
    analysis = workspace(tmp_path)
    rows = [{'causal_analysis': analysis}, {'causal_analysis': analysis}]
    assert _helper_provenance(tmp_path, rows, 'core.py:Worker.convert')['status'] == 'current'
    write(tmp_path, 'core.py', 'class Worker:\n    def convert(self, value): return "changed"\n')
    assert _helper_provenance(tmp_path, rows, 'core.py:Worker.convert')['status'] == 'stale'


def test_same_named_absolute_module_cannot_capture_helper(tmp_path):
    write(tmp_path, 'utils.py', 'def render(value): return value\n')
    assert workspace(tmp_path)['production_targets'] == ['core.py:Worker.convert']


def test_nested_options_and_local_names_are_not_method_overrides(tmp_path):
    result = workspace(tmp_path, production='class Worker:\n    class Options:\n        convert = None\n'
                       '    def convert(self, value): return value\n    def other(self):\n        convert = None\n')
    assert result['production_targets'] == ['core.py:Worker.convert']


def test_multiple_observed_apis_remain_ambiguous(tmp_path):
    workspace(tmp_path)
    write(tmp_path, 'other.py', 'class Worker:\n    def convert(self, value): return value\n')
    write(tmp_path, 'tests/other_utils.py', 'from other import Worker\ndef render(value): return Worker().convert(value)\n')
    write(tmp_path, 'tests/test_case.py', 'from .utils import render\nfrom .other_utils import render as second\n'
          'def test_case():\n    assert render("x") == "y"\n    assert second("x") == "y"\n')
    result = _test_assertion_causal_analysis(tmp_path, ['tests/test_case.py::test_case'])
    assert not result['production_targets']
    assert len(result['candidate_targets']) == 2


def test_opaque_assertion_observer_cannot_promote_helper(tmp_path):
    workspace(tmp_path)
    write(tmp_path, 'tests/test_case.py', 'from .utils import render\nfrom external import observe\n'
          'def test_case(): assert observe(render("x")) == "y"\n')
    assert not _test_assertion_causal_analysis(tmp_path, ['tests/test_case.py::test_case'])['production_targets']


@pytest.mark.parametrize('where', ['helper', 'test'])
def test_method_mutation_in_test_support_cannot_bind(tmp_path, where):
    workspace(tmp_path)
    name = 'tests/utils.py' if where == 'helper' else 'tests/test_case.py'
    path = tmp_path / name
    path.write_text(path.read_text() + '\nfrom core import Worker\nWorker.convert = lambda self, value: value\n', encoding='utf-8')
    assert not _test_assertion_causal_analysis(tmp_path, ['tests/test_case.py::test_case'])['production_targets']


def test_shadowed_object_base_is_not_assumed_builtin(tmp_path):
    assert not workspace(tmp_path, production='from other import Strange as object\nclass Worker(object):\n'
                         '    def convert(self, value): return value\n')['production_targets']


def test_instance_dictionary_override_is_not_an_ordinary_method(tmp_path):
    assert not workspace(tmp_path, production='class Worker:\n    def __init__(self, **options):\n'
        '        self.__dict__.update(options)\n    def convert(self, value): return value\n')['production_targets']


def test_native_replay_reproduces_the_observed_helper_method(tmp_path):
    workspace(tmp_path, production='class Worker:\n    def __init__(self, **options): pass\n'
              '    def convert(self, value): return value\n')
    settings = {'local_editable_install': False, 'timeout_seconds': 20,
                'pytest_arguments': ['-q', '--tb=short', '--color=no', '-p', 'no:cacheprovider', '-o', 'addopts=']}
    rows = [_run_pytest(tmp_path, settings, nodeids=['tests/test_case.py']) for _ in range(2)]
    assert all(r['status'] == 'test_failed' and r['leaf_production_target'] == 'core.py:Worker.convert' for r in rows)
    assert rows[0]['failure_signature'] == rows[1]['failure_signature']
