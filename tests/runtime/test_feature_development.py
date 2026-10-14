"""Feature workflow authority and real native comparison, across neutral fixtures."""
from pathlib import Path
import sys

import pytest

from runtime.feature_development import run_feature_development
from runtime.feature_workspace import digest, install, inventory, materialize_edits, read_sources
from runtime.local_inference import LocalInferenceConfig


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'sample'
    (root / 'tests').mkdir(parents=True)
    (root / 'engine.py').write_text('def display(value):\n    return str(value)\n', encoding='utf-8')
    (root / 'tests/test_existing.py').write_text(
        'from engine import display\ndef test_positive():\n    assert display(3) == "3"\n', encoding='utf-8')
    return root


def spec():
    return {'status': 'ready', 'acceptance': ['negative labels are parenthesized'],
        'limitations': ['no UI rendering test'], 'environment': {},
        'tests': [{'path': 'tests/test_labels.py', 'content':
            'from engine import display\ndef test_negative():\n    assert display(-2) == "(2)"\n'}],
        'regression_tests': ['tests/test_existing.py']}


def fake_chat(project, *, bad=False, review='approve', mutate=False):
    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role == 'analyzer':
            return {'status': 'ready', 'analysis': 'missing negative labels', 'scope': ['engine.py'],
                    'evidence': [], 'unknowns': [], 'user_outcome': 'negative labels'}
        if role == 'architect':
            return {'status': 'ready', 'design': 'branch on negative', 'scope': ['engine.py'],
                    'preserve': ['positive'], 'risks': [], 'acceptance': ['negative labels']}
        if role == 'spec_writer':
            return spec()
        if role == 'programmer':
            return {'status': 'ready', 'edits': [{'path': 'engine.py',
                'source_sha256': digest((project / 'engine.py').read_bytes()),
                'replacements': [{'old': 'return str(value)',
                    'new': 'return "broken"' if bad else
                           'return f"({-value})" if value < 0 else str(value)'}]}]}
        if mutate:
            (project / 'engine.py').write_text('# concurrent edit\n', encoding='utf-8')
        return {'status': 'ready', 'decision': review, 'reason': 'checked',
                'delivered_scope': 'negative labels', 'limitations': ['no visual test'],
                'goal_complete': False}
    return chat


def run(project, tmp_path, **kwargs):
    config = LocalInferenceConfig('http://unused', 'fake')
    return run_feature_development(project=project, work=tmp_path / 'run',
        goal='Improve negative display labels', python=Path(sys.executable),
        configs={r: config for r in ('analyzer', 'architect', 'spec_writer')}, **kwargs)


def test_real_comparison_and_cos_install(project, tmp_path):
    result = run(project, tmp_path, chat=fake_chat(project), apply_source=True)
    assert result['status'] == 'installed', result
    assert result['baseline']['new_tests']['counts']['failed'] == 1
    assert result['attempts'][0]['counts']['passed'] == 2
    assert result['installation']['writer'] == 'runtime.feature_workspace.install'
    assert (project / 'tests/test_labels.py').is_file()
    assert not result['goal_complete']


@pytest.mark.parametrize('bad,review', [(True, 'approve'), (False, 'reject')])
def test_failed_code_or_review_never_applies(project, tmp_path, bad, review):
    before = inventory(project)
    result = run(project, tmp_path, chat=fake_chat(project, bad=bad, review=review), apply_source=True)
    assert result['status'] == 'blocked'
    assert not result['source_apply'] and inventory(project) == before


def test_verified_without_write_authority(project, tmp_path):
    before = inventory(project)
    result = run(project, tmp_path, chat=fake_chat(project))
    assert result['status'] == 'verified'
    assert not result['source_apply'] and inventory(project) == before


def test_concurrent_source_edit_is_not_overwritten(project, tmp_path):
    result = run(project, tmp_path, chat=fake_chat(project, mutate=True), apply_source=True)
    assert result['reason'] == 'feature_original_source_changed'
    assert (project / 'engine.py').read_text() == '# concurrent edit\n'


def test_install_rolls_back_partial_write(project, tmp_path, monkeypatch):
    import runtime.feature_workspace as module
    before = inventory(project)
    atomic = module._atomic_write
    def failing(path, data):
        if path == project / 'later.py':
            raise OSError('simulated failure')
        atomic(path, data)
    monkeypatch.setattr(module, '_atomic_write', failing)
    with pytest.raises(OSError):
        install(project, before, {'engine.py': b'# changed', 'later.py': b'pass'}, tmp_path / 'backup')
    assert inventory(project) == before
    assert not (project / '.cos-feature.lock').exists()


def test_sources_reject_escape_and_stale_hash(project):
    before = inventory(project)
    with pytest.raises(ValueError):
        read_sources(project, before, [{'path': '../private.py'}])
    (project / 'engine.py').write_text('# changed')
    with pytest.raises(ValueError, match='source_changed'):
        read_sources(project, before, [{'path': 'engine.py'}])


def test_coder_cannot_modify_frozen_tests(project):
    with pytest.raises(ValueError, match='edit_scope'):
        materialize_edits(project, inventory(project), [{'path': 'tests/test_existing.py'}],
                          ['tests/test_existing.py'])


def test_project_rename_does_not_change_workflow(project, tmp_path):
    renamed = project.rename(tmp_path / 'unrelated_product')
    result = run(renamed, tmp_path, chat=fake_chat(renamed))
    assert result['status'] == 'verified'


def test_empty_or_already_passing_new_tests_do_not_qualify(project, tmp_path):
    delegate = fake_chat(project)
    def chat(messages, *, config):
        result = delegate(messages, config=config)
        if config.provider_label == 'feature:spec_writer':
            result['tests'][0]['content'] = 'def test_trivial():\n    assert True\n'
        return result
    result = run(project, tmp_path, chat=chat, apply_source=True)
    assert result['reason'] == 'feature_baseline_not_qualified'
    assert not result['source_apply']


def test_large_reads_are_explicitly_paged_not_silently_complete(project):
    (project / 'large.py').write_text('value = 1\n' * 200, encoding='utf-8')
    rows = read_sources(project, inventory(project), [{'path': 'large.py'}], max_bytes=100)
    assert rows[0]['truncated'] is True
    assert rows[0]['end'] == 10 and rows[0]['requested_end'] == 200
    assert len(rows[0]['content'].encode('utf-8')) == 100


def test_crlf_source_replacement_preserves_line_endings(project):
    path = project / 'engine.py'
    path.write_bytes(b'def display(value):\r\n    return str(value)\r\n')
    before = inventory(project)
    proposal = [{'path': 'engine.py', 'source_sha256': before['engine.py'],
                 'replacements': [{'old': '    return str(value)\n', 'new': '    return repr(value)\n'}]}]
    edits = materialize_edits(project, before, proposal, ['engine.py'])
    assert edits['engine.py'] == b'def display(value):\r\n    return repr(value)\r\n'


def test_inventory_excludes_archives_outputs_and_machine_secrets(project):
    for name in ['legacy/history.py', 'sample_outputs/result.json', 'config.json',
                 '.env', 'credentials.json']:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}', encoding='utf-8')
    assert set(inventory(project)) == {'engine.py', 'tests/test_existing.py'}


def test_repeated_read_loop_stops_without_writes(project, tmp_path):
    calls = []
    def chat(messages, *, config):
        calls.append(config.provider_label)
        return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
    result = run(project, tmp_path, chat=chat, apply_source=True)
    assert result['reason'] == 'feature_repeated_read_without_progress:analyzer'
    assert len(calls) == 3 and not result['source_apply']


def test_resume_context_rechecks_source_instead_of_trusting_cached_text(project, tmp_path):
    from runtime.feature_acceptance import save
    old = tmp_path / 'old'
    expected = inventory(project)
    save(old / 'source-inventory.json', expected)
    save(old / 'source-context.json', {'goal': 'Improve negative display labels',
        'sources': [{'path': 'engine.py', 'start': 1, 'end': 2,
                     'content': 'UNTRUSTED REPLACEMENT', 'sha256': 'wrong'}]})
    seen = []
    delegate = fake_chat(project)
    def chat(messages, *, config):
        seen.append(messages[1]['content'])
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat, resume_context=old)
    assert result['status'] == 'verified'
    assert all('UNTRUSTED REPLACEMENT' not in row for row in seen)


def test_incomplete_read_response_receives_bounded_automatic_feedback(project, tmp_path):
    delegate = fake_chat(project)
    first = True
    def chat(messages, *, config):
        nonlocal first
        if first:
            first = False
            return {'status': 'read'}
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified'


def test_broken_generated_test_is_not_a_proven_product_gap(project, tmp_path):
    delegate = fake_chat(project)
    def chat(messages, *, config):
        result = delegate(messages, config=config)
        if config.provider_label == 'feature:spec_writer':
            result['tests'][0]['content'] = (
                'def test_broken():\n    raise RuntimeError("fixture bug")\n    assert True\n')
        return result
    result = run(project, tmp_path, chat=chat, apply_source=True)
    assert result['reason'] == 'feature_baseline_not_qualified'
    assert not result['source_apply']


def test_architect_test_mentions_cannot_grant_existing_test_write_authority(project, tmp_path):
    delegate = fake_chat(project)
    original = (project / 'tests/test_existing.py').read_bytes()
    def chat(messages, *, config):
        result = delegate(messages, config=config)
        if config.provider_label == 'feature:architect':
            result['scope'].append('tests/test_existing.py')
        return result
    result = run(project, tmp_path, chat=chat, apply_source=True)
    assert result['status'] == 'installed'
    architecture = result['artifacts']['architect']
    assert architecture['scope'] == ['engine.py']
    assert architecture['non_writable_test_context'] == ['tests/test_existing.py']
    assert (project / 'tests/test_existing.py').read_bytes() == original


def test_spec_read_does_not_expand_to_all_previously_cached_file_lines(project, tmp_path):
    import json
    delegate = fake_chat(project)
    counts = {}
    def chat(messages, *, config):
        role = config.provider_label.partition(':')[2]
        counts[role] = counts.get(role, 0) + 1
        if role == 'analyzer' and counts[role] == 1:
            return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
        if role == 'spec_writer':
            if counts[role] == 1:
                return {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 1}]}
            payload = json.loads(messages[1]['content'])
            assert payload['sources'][0]['start'] == payload['sources'][0]['end'] == 1
            assert 'return str' not in payload['sources'][0]['content']
        return delegate(messages, config=config)
    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified', result
