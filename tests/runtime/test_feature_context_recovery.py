"""Context recovery keeps requested evidence and separates drafts from files."""
import json

import pytest

from runtime.feature_context import select_context
from runtime.feature_context_reads import read_request
from runtime.feature_workspace import catalog, inventory, read_sources
from tests.runtime.test_feature_development import project, fake_chat, run


def test_missing_name_returns_feedback_and_valid_sibling_read(project, tmp_path):
    delegate, seen = fake_chat(project), []

    def chat(messages, *, config):
        if config.provider_label == 'feature:spec_writer':
            payload = json.loads(messages[1]['content'])
            seen.append(payload)
            if len(seen) == 1:
                return {'status': 'read', 'reads': [{'path': 'wrong_engine.py'}, {'path': 'engine.py'}]}
            assert payload['read_tool_result']['errors'][0]['path'] == 'wrong_engine.py'
            assert any(r['path'] == 'engine.py' and 'def display' in r['content'] for r in payload['sources'])
            assert {r['path'] for r in payload['catalog']} == set(inventory(project))
        return delegate(messages, config=config)

    result = run(project, tmp_path, chat=chat)
    assert result['status'] == 'verified', result
    assert len(seen) == 2


@pytest.mark.parametrize('name', ['../escape.py', '.env', 'config.json', 'secret.py', 'untracked.py'])
def test_read_recovery_does_not_admit_private_or_uninventoried_files(project, name):
    expected = inventory(project)
    (project / 'untracked.py').write_text('value = 1')
    with pytest.raises(ValueError):
        read_request(project, expected, [{'path': name}])


def test_source_hash_mismatch_is_fatal_even_with_missing_sibling(project):
    expected = inventory(project)
    (project / 'engine.py').write_text('changed = True')
    with pytest.raises(ValueError, match='feature_source_changed'):
        read_request(project, expected, [{'path': 'missing.py'}, {'path': 'engine.py'}])


@pytest.mark.parametrize('extension', [None, {'spec': {'regression_tests': ['tests/test_existing.py']}}])
def test_explicit_reads_survive_selection_even_outside_scope(project, extension, monkeypatch):
    import runtime.feature_context as module
    monkeypatch.setattr(module, 'extension_context', lambda value: {})
    (project / 'tests/fixture.json').write_text('{"data":"exact"}')
    expected = inventory(project)
    requested = read_sources(project, expected, [{'path': 'tests/fixture.json'}, {'path': 'tests/test_existing.py'}])
    ctx = {'sources': requested, 'catalog': catalog(project, expected)}
    artifacts = {'analyzer': {'evidence': []}, 'architect': {'scope': ['engine.py']}}
    payload = select_context({**ctx, 'artifacts': artifacts}, role='spec_writer', ctx=ctx,
        artifacts=artifacts, extra={'feedback': 'repair'}, role_reads=requested, fresh_reads=[],
        recent_paths=set(), extension=extension, spec_format='python', project=project,
        expected=expected, observed={'files': []})
    fields = ('path', 'sha256', 'start', 'end', 'content')
    assert [{k: r[k] for k in fields} for r in payload['sources']] == [
        {k: r[k] for k in fields} for r in requested]
    assert {r['path'] for r in payload['catalog']} == set(expected)


def test_unrequested_test_background_is_readable_without_automatic_resend(project):
    expected = inventory(project)
    ctx = {'sources': read_sources(project, expected, [{'path': 'tests/test_existing.py'}]),
           'catalog': catalog(project, expected)}
    artifacts = {'analyzer': {'evidence': []}, 'architect': {'scope': ['engine.py']}}
    payload = select_context({**ctx}, role='spec_writer', ctx=ctx, artifacts=artifacts,
        extra=None, role_reads=[], fresh_reads=[], recent_paths=set(), extension=None,
        spec_format='python', project=project, expected=expected, observed={'files': []})
    assert not payload['sources']
    assert 'tests/test_existing.py' in {r['path'] for r in payload['catalog']}


def test_partial_test_suite_is_completed_for_ast_admission(project):
    from runtime.feature_context import complete_test_fragments
    from plugins.development_quality.src.main import validate
    from tests.runtime.test_feature_development import spec
    from tests.runtime.test_feature_quality import augment
    name = 'tests/test_existing.py'
    text = 'class Helper:\n    value = 1\n\ndef test_positive():\n    assert 3 > 2\n'
    (project / name).write_text(text)
    expected = inventory(project)
    fragment = read_sources(project, expected, [{'path': name, 'start': 2, 'end': 5}])
    proposal = augment('spec_writer', spec())
    proposal['case_plan'][1]['node'] = name + '::test_positive'
    assert validate('spec_writer', proposal, fragment)
    sources = complete_test_fragments(project, expected, fragment)
    assert sources[0]['content'] == text
    assert not validate('spec_writer', proposal, sources)


def test_completion_checks_original_source_hash(project):
    from runtime.feature_context import complete_test_fragments
    expected = inventory(project)
    fragment = [{'path': 'tests/test_existing.py', 'start': 3, 'end': 3,
                 'content': '    assert display(3) == "3"\n'}]
    (project / 'tests/test_existing.py').write_text('changed = 1')
    with pytest.raises(ValueError, match='feature_source_changed'):
        complete_test_fragments(project, expected, fragment)
