"""task_competency.v1: explicit applicability, generated oracle and patch for one target."""
import pickle
import sys
import types

from runtime.competency_knowledge import invoke_knowledge

SOURCE = '''class FetchError(Exception):
    def __init__(self, url, status):
        self.url = url
        self.status = status
        super().__init__(f"{url} failed with {status}")


class ParseError(ValueError):
    def __init__(self, line):
        self.line = line
        super().__init__("bad line " + str(line))
'''


def _call(goal, sources):
    return invoke_knowledge('exception_pickle', {'operation': 'task_change', 'goal': goal, 'sources': sources})


def test_goal_must_request_pickling():
    result = _call('Add retry with backoff', [{'path': 'pkg/errors.py', 'content': SOURCE}])
    assert result == {'status': 'not_applicable', 'reason': 'goal_does_not_request_pickle_support'}


def test_several_candidates_require_a_named_target():
    sources = [{'path': 'pkg/errors.py', 'content': SOURCE}]
    assert _call('Make errors picklable', sources)['reason'].startswith('ambiguous_target:')
    result = _call('Make ParseError picklable', sources)
    assert result['status'] == 'proposed' and result['change']['target'] == 'pkg/errors.py:ParseError'


def test_tests_are_never_treated_as_production_targets():
    result = _call('Make FetchError picklable', [{'path': 'tests/test_errors.py', 'content': SOURCE}])
    assert result['reason'] == 'no_supported_unpicklable_exception_in_sources'


def test_generated_oracle_is_red_on_original_and_green_on_patch(tmp_path, monkeypatch):
    change = _call('Make FetchError picklable', [{'path': 'src/pkg/errors.py', 'content': SOURCE}])['change']
    assert change['contract'] == 'task_competency.v1' and change['tests'][0]['path'] == 'tests/test_cos_pickle_fetch_error.py'
    test_source = change['tests'][0]['content']
    assert "parents[1] / 'src'" in test_source and 'from pkg.errors import FetchError' in test_source
    for label, module_source, passes in (('original', SOURCE, False), ('patched', change['edits'][0]['content'], True)):
        package = types.ModuleType('pkg')
        package.__path__ = []
        module = types.ModuleType('pkg.errors')
        exec(module_source, module.__dict__)
        monkeypatch.setitem(sys.modules, 'pkg', package)
        monkeypatch.setitem(sys.modules, 'pkg.errors', module)
        namespace = {'__file__': str(tmp_path / 'tests' / 'test_x.py'), '__name__': 'generated_' + label}
        exec(test_source, namespace)
        try:
            namespace['test_fetch_error_pickle_round_trip_preserves_state']()
            outcome = True
        except AssertionError:
            outcome = False
        assert outcome is passes, label
    restored = pickle.loads(pickle.dumps(module.FetchError('u', 5)))
    assert restored.url == 'u' and restored.status == 5
