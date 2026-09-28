"""A byte-identical echoed frozen test does not grant Programmer test authorship."""
import pytest

from runtime.feature_workspace import materialize_edits, inventory, proposal_for_context
from tests.runtime.test_feature_development import project, fake_chat, run, spec


@pytest.mark.parametrize('change', [None, 'content', 'hash', 'extra', 'duplicate', 'only_tests'])
def test_only_exact_frozen_echo_is_ignored(project, tmp_path, change):
    expected = inventory(project)
    item = {'path': 'tests/test_labels.py', 'source_sha256': None, 'content': spec()['tests'][0]['content']}
    frozen = {item['path']: item['content'].encode()}
    production = {'path': 'engine.py', 'source_sha256': expected['engine.py'],
                  'replacements': [{'old': 'str(value)', 'new': 'repr(value)'}]}
    if change == 'content': item['content'] += '\n# not frozen\n'
    if change == 'hash': item['source_sha256'] = 'hash'
    if change == 'extra': item['replacements'] = []
    proposals = [item, production]
    if change == 'duplicate': proposals.insert(0, item)
    if change == 'only_tests': proposals = [item]
    if change:
        with pytest.raises(ValueError):
            materialize_edits(project, expected, proposals, ['engine.py'], frozen_tests=frozen)
    else:
        result = materialize_edits(project, expected, proposals, ['engine.py'], frozen_tests=frozen)
        assert list(result) == ['engine.py']
        context = proposal_for_context({'edits': proposals}, frozen)
        assert context['edits'] == [production]
        assert context['exact_frozen_test_echoes'][item['path']]
    assert inventory(project) == expected


def test_pipeline_keeps_original_proposal_and_frozen_acceptance(project, tmp_path):
    delegate = fake_chat(project)
    def chat(messages, *, config):
        value = delegate(messages, config=config)
        if config.provider_label == 'feature:programmer':
            value['edits'].append({**spec()['tests'][0], 'source_sha256': None})
        return value
    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified'
    assert result['exact_frozen_test_echoes'] == ['tests/test_labels.py']
    assert (tmp_path / 'run/attempt-1/project/tests/test_labels.py').read_bytes() == spec()['tests'][0]['content'].encode()
