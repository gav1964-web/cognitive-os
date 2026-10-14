import pytest

from runtime.programmer_mapping_descent_patch import guard_mapping_path_descent
from runtime.programmer_patch_synthesizer_core import synthesize_patch_package

SOURCE = '''class Store:
    def lookup(self, path, default=None):
        """Return default if the full path is absent."""
        parts = path.strip('/').split('/')
        current: dict = self.tree
        for part in parts:
            if part not in current:
                return default
            sub = current[part]
            if not isinstance(sub, dict):
                return sub
            current = sub
        return current
'''


@pytest.mark.parametrize('leaf', ['abc', 42, False, None, ['child'], {}, {'present': 7}])
def test_complete_path_is_required_and_existing_values_preserved(leaf):
    result = guard_mapping_path_descent(SOURCE, 'Store.lookup')
    namespace = {}
    exec(result['source'], namespace)
    store = namespace['Store']()
    store.tree = {'app': {'value': leaf}}
    sentinel = object()
    assert store.lookup('/app/value/missing', sentinel) is sentinel
    assert store.lookup('/app/value', sentinel) is leaf
    assert store.lookup('/app', sentinel) is store.tree['app']
    assert store.lookup('/absent', sentinel) is sentinel


@pytest.mark.parametrize('source,symbol', [
    (SOURCE, 'Other.lookup'), (SOURCE, 'lookup'), ('invalid!', 'Store.lookup'),
    (SOURCE.replace('return sub', 'return default'), 'Store.lookup'),
    (SOURCE.replace('current = sub', 'current = transform(sub)'), 'Store.lookup'),
    (SOURCE.replace('return sub', 'return sub\n            log(sub)'), 'Store.lookup'),
    (SOURCE.replace('self.tree', 'self.make_tree()'), 'Store.lookup'),
    (SOURCE.replace('default=None', 'default=None, dict=dict'), 'Store.lookup'),
    ('dict = list\n' + SOURCE, 'Store.lookup'),
    ('from custom import isinstance\n' + SOURCE, 'Store.lookup'),
    ('from custom import *\n' + SOURCE, 'Store.lookup'),
    (SOURCE.replace('    def lookup', '    @decorator\n    def lookup'), 'Store.lookup'),
    (SOURCE.replace('return current', 'return None'), 'Store.lookup'),
])
def test_unknown_shapes_and_shadowed_builtins_are_rejected(source, symbol):
    assert guard_mapping_path_descent(source, symbol) is None


@pytest.mark.parametrize('authorized', [False, True])
def test_authority_and_source_invariance(tmp_path, authorized):
    project = tmp_path / 'project'
    project.mkdir()
    original = project / 'store.py'
    original.write_text(SOURCE, encoding='utf-8')
    operator = 'guard_mapping_path_descent'
    intent = {'operator_id': operator, 'allowed_operator_ids': [operator]}
    if authorized:
        intent['authority'] = 'explicit_training_replay'
    target = 'store.py:Store.lookup'
    result = synthesize_patch_package(execution_dir=tmp_path / 'execution', project_dir=project,
        implementation_plan={'implementation_target': {'candidate': target},
            'patch_intent': {'target_symbol': target}, 'expected_files': ['store.py'],
            'implementation_delta': {'status': 'ready', 'intent': intent}}, test_plan={})
    assert result['status'] == ('prepared' if authorized else 'blocked')
    assert original.read_text(encoding='utf-8') == SOURCE
    if not authorized:
        assert result['reason'] == 'training_replay_authority_required'


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_training_package_preserves_probed_patch_bytes(tmp_path, newline):
    from pathlib import Path
    from runtime.programmer_patch_synthesizer_training import training_repair_package
    project = tmp_path / 'project'
    project.mkdir()
    source = SOURCE.replace('\n', newline)
    (project / 'store.py').write_bytes(source.encode('utf-8'))
    expected = guard_mapping_path_descent(source, 'Store.lookup')['source'].encode('utf-8')
    result = training_repair_package(execution_dir=tmp_path / 'execution', project_dir=project,
        target='store.py:Store.lookup', path_text='store.py', symbol='Store.lookup',
        operation_kind='guard_mapping_path_descent')
    assert (Path(result['sandbox_project']) / 'store.py').read_bytes() == expected
    assert (project / 'store.py').read_bytes() == source.encode('utf-8')
