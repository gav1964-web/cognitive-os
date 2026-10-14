"""Review sees actual materialized bytes and can distinguish them from source."""
import json

import pytest

from runtime.feature_review_patch import candidate_patch
from runtime.feature_workspace import digest, inventory
from tests.runtime.test_feature_development import project, fake_chat, run


def test_review_gets_diff_and_candidate_hash(project, tmp_path):
    delegate = fake_chat(project)

    def chat(messages, *, config):
        if config.provider_label == 'feature:reviewer':
            payload = json.loads(messages[1]['content'])
            row = payload['candidate_patch'][0]
            assert row['path'] == 'engine.py'
            assert row['source_sha256'] == digest((project / 'engine.py').read_bytes())
            assert '-    return str(value)' in row['unified_diff']
            assert '+    return f"({-value})" if value < 0 else str(value)' in row['unified_diff']
            candidate = tmp_path / 'run/attempt-1/project/engine.py'
            assert row['candidate_sha256'] == digest(candidate.read_bytes())
        return delegate(messages, config=config)

    assert run(project, tmp_path, chat=chat)['status'] == 'verified'


def test_review_diff_rejects_stale_original_and_supports_new_file(project):
    expected = inventory(project)
    rows = candidate_patch(project, expected, {'new.py': b'x = 1\n'})
    assert rows[0]['source_sha256'] is None and '+x = 1' in rows[0]['unified_diff']
    (project / 'engine.py').write_text('changed = True\n')
    with pytest.raises(ValueError, match='feature_review_patch_stale_source'):
        candidate_patch(project, expected, {'engine.py': b'x = 1\n'})
