"""README lookups retain documentation authority and the source-read limits."""
import hashlib
import json
from pathlib import Path

import pytest

from plugins.project_description.src.main import run
from plugins.project_description.src.claim_evidence import literal_matches
from runtime.project_description import describe_project
from runtime.project_description_review import draft_claims

ROOT = Path(__file__).resolve().parents[2]


def request(path, **extra):
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **extra}


@pytest.mark.parametrize('name', ['README.md', 'Readme.rst', 'readme.txt', 'README'])
def test_readme_ranges_are_bounded_redacted_and_never_code_facts(tmp_path, name):
    path = tmp_path / name
    path.write_text('# API\nTOKEN = "SECRET_CANARY"\nDocumented feature\n', encoding='utf-8')
    result = run({'project_root': str(tmp_path), 'action': 'read',
                  'requests': [request(path, start_line=2, end_line=3)]})
    source = result['evidence']['sources'][0]
    assert source['authority'] == 'documentation_claims'
    assert 'SECRET_CANARY' not in source['excerpt'] and 'Documented feature' in source['excerpt']
    assert '# API' not in source['excerpt']
    assert literal_matches('Documented feature', [source]) == []
    with pytest.raises(ValueError, match='symbol_requires_python'):
        run({'project_root': str(tmp_path), 'action': 'read', 'requests': [request(path, symbol='API')]})
    with pytest.raises(ValueError, match='line_range'):
        run({'project_root': str(tmp_path), 'action': 'read', 'requests': [request(path, start_line=1, end_line=302)]})
    bound = request(path)
    path.write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='source_changed'):
        run({'project_root': str(tmp_path), 'action': 'read', 'requests': [bound]})


@pytest.mark.parametrize('name', ['notes.md', 'README.json', '.README.md', 'credentials.json'])
def test_document_lookup_does_not_admit_arbitrary_files(tmp_path, name):
    path = tmp_path / name
    path.write_text('not an allowed source', encoding='utf-8')
    with pytest.raises(ValueError, match='lookup_path'):
        run({'project_root': str(tmp_path), 'action': 'read', 'requests': [request(path)]})


def test_review_can_complete_after_code_and_document_lookup(tmp_path):
    (tmp_path / 'app.py').write_text('def run():\n    return 1\n', encoding='utf-8')
    (tmp_path / 'README.md').write_text('# API\n## Contract\nDOCUMENT_CANARY\n', encoding='utf-8')
    calls = []
    claim = {'text': 'Returns one.', 'evidence_ids': ['s1']}
    draft = {'purpose': claim, 'scenarios': [dict(claim)], 'data_flow': [dict(claim)],
             'unknowns': [], 'confidence': 'medium'}
    def chat(messages, *, config):
        calls.append(messages)
        if len(calls) == 1:
            return draft
        if len(calls) == 2:
            return {'requests': [{'path': 'app.py', 'symbol': 'run'},
                                 {'path': 'README.md', 'start_line': 1, 'end_line': 50}]}
        payload = json.loads(messages[1]['content'])
        doc = next(s for s in payload['evidence']['sources'] if s['id'] == 'x2')
        assert doc['authority'] == 'documentation_claims' and 'DOCUMENT_CANARY' in doc['excerpt']
        return {'description': draft, 'corrections': [], 'claim_reviews': [
            {'claim_id': c['id'], 'action': 'retained', 'reason': 'Code returns one.', 'evidence_ids': ['x1']}
            for c in draft_claims(draft)]}
    result = describe_project(tmp_path, chat=chat)
    assert result['status'] == 'described' and len(calls) == 3
    assert result['lookup_history'][1]['source_id'] == 'x2'
