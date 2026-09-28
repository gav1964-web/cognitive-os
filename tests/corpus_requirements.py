"""Explicit prerequisites for dated local-corpus integration measurements."""
import json

import pytest


def require_files(root, paths):
    missing = [name for name in paths if not (root / name).is_file()]
    if missing:
        pytest.skip('local_corpus integration data unavailable: ' + ', '.join(missing[:3]))


def require_policy_corpus(root, name):
    policy = json.loads((root / 'config' / name).read_text(encoding='utf-8'))
    paths = [row['path'] for row in policy.get('sources', [])]
    paths.extend(policy[key] for key in ('maturity_matrix', 'prospective_report', 'collector_checkpoint') if key in policy)
    require_files(root, paths)


def require_boundary_contrast(root, hypothesis_kind):
    from runtime.project_development_boundary_interpreter import load_source_contrasts
    policy = load_source_contrasts(root=root)
    rows = [row for row in policy['contrasts'] if row['hypothesis_kind'] == hypothesis_kind]
    assert rows, 'the requested contrast must remain declared'
    require_files(root, [name for row in rows for name in (
        row['project_path'] + '/' + row['target'].split(':', 1)[0],
        'artifacts/project_development/' + row['validation_report'])])
