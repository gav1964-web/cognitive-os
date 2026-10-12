from copy import deepcopy
import json
import pytest
from runtime.feature_frozen_references import reference_catalog, expand_frozen_references


def test_only_missing_reference_digest_can_be_restored_without_test_changes():
    from runtime.feature_frozen_references import repair_reference_metadata
    frozen = [{'path': 'tests/test_x.py', 'content': '# α\r\nassert f()\r\n'}]
    raw = {'tests': [{'path': frozen[0]['path'], 'content_reference': 'immutable_previous_tests'}]}
    normalized, changes = repair_reference_metadata(raw, frozen)
    assert 'content_sha256' not in raw['tests'][0] and len(changes) == 1
    assert expand_frozen_references(normalized, frozen) == ({'tests': frozen}, 1)
    for invalid in [{**raw['tests'][0], 'content_sha256': 'wrong'},
                    {**raw['tests'][0], 'path': 'tests/unknown.py'},
                    {**raw['tests'][0], 'content': 'assert changed()'},
                    {**raw['tests'][0], 'content_reference': 'unaccepted'}]:
        value = {'tests': [invalid]}
        assert repair_reference_metadata(value, frozen) == (value, [])
        with pytest.raises(ValueError, match='frozen_reference'):
            expand_frozen_references(value, frozen)
    assert repair_reference_metadata(raw, frozen + frozen) == (raw, [])


def test_output_reference_restores_exact_model_authored_bytes():
    frozen = [{'path': 'tests/test_x.py', 'content': '# Unicode \u03b1\r\n' * 500}]
    raw = {'tests': reference_catalog(frozen) + [{'path': 'tests/test_new.py', 'content': 'assert f()\n'}]}
    before = deepcopy(raw)
    expanded, count = expand_frozen_references(raw, frozen)
    assert raw == before and count == 1
    assert expanded['tests'][0] == frozen[0]
    assert len(json.dumps(raw)) < len(json.dumps(expanded)) / 10


@pytest.mark.parametrize('change', [
    {'content_sha256': 'stale'}, {'path': 'tests/test_unknown.py'},
    {'content_reference': 'unaccepted_draft'}, {'content': 'assert True'},
])
def test_reference_cannot_change_tests_or_promote_other_drafts(change):
    frozen = [{'path': 'tests/test_x.py', 'content': 'assert f()\n'}]
    row = {**reference_catalog(frozen)[0], **change}
    with pytest.raises(ValueError, match='frozen_reference'):
        expand_frozen_references({'tests': [row]}, frozen)


@pytest.mark.parametrize('separate', [False, True])
def test_reference_output_enters_normal_audit_with_full_tests(tmp_path, separate):
    from runtime.feature_quality_chat import QualityChat
    from runtime.local_inference import LocalInferenceConfig
    from tests.runtime.test_feature_development import spec
    from tests.runtime.test_feature_quality import augment
    from runtime.feature_test_references import expand_test_references
    proposal = augment('spec_writer', spec())
    frozen = proposal['tests']
    calls = []
    def chat(messages, *, config):
        payload = json.loads(messages[1]['content'])
        if 'test_reference_contract' in payload:payload = expand_test_references(payload)
        calls.append(config.provider_label)
        if config.provider_label == 'feature:spec_writer':
            if separate:
                return {**proposal, 'tests': [], 'immutable_test_refs': payload['immutable_test_refs']}
            return {**proposal, 'tests': payload['immutable_test_refs']}
        assert payload['specification']['tests'] == frozen
        assert payload['accepted_test_paths'] == [t['path'] for t in frozen]
        return {'decision': 'approve'}
    q = QualityChat(chat, tmp_path)
    q.frozen = frozen
    result = q([{'role':'system','content':'spec'}, {'role':'user','content':json.dumps({
        'goal':'labels','sources':[],'artifacts':{'architect':{}}})}],
        config=LocalInferenceConfig('http://unused','fake',provider_label='feature:spec_writer'))
    assert result == proposal and len(calls) == 2
    assert (tmp_path/'frozen-refs-0-0.json').exists()


@pytest.mark.parametrize('case', ['valid', 'wrong_hash', 'duplicate', 'literal', 'wrong_path', 'nonlist'])
def test_separate_reference_envelope_is_exact_unambiguous_and_versioned(case):
    frozen = [{'path': 'tests/test_x.py', 'content': '# unicode α\r\nassert f()\r\n'}]
    refs = reference_catalog(frozen)
    raw = {'tests': [], 'immutable_test_refs': refs}
    if case == 'wrong_hash': refs[0]['content_sha256'] = 'wrong'
    if case == 'duplicate': raw['tests'] = deepcopy(frozen)
    if case == 'literal': refs[0]['content'] = 'assert True'
    if case == 'wrong_path': refs[0]['path'] = 'tests/unaccepted.py'
    if case == 'nonlist': raw['immutable_test_refs'] = {}
    before = deepcopy(raw)
    assert expand_frozen_references(raw, frozen) == (raw, 0)  # Historical receipt semantics.
    if case == 'valid':
        assert expand_frozen_references(raw, frozen, allow_separate=True) == ({'tests': frozen}, 1)
    else:
        with pytest.raises(ValueError, match='frozen_reference'):
            expand_frozen_references(raw, frozen, allow_separate=True)
    assert raw == before
