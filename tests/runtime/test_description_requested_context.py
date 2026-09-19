"""Requested long workflows survive review allocation; unread text stays explicit."""
import json
from pathlib import Path

from plugins.project_description.src.claim_evidence import review_context
from plugins.project_description.src.main import run
from plugins.project_description.src.source_lookup import read_requests
import hashlib

ROOT = Path(__file__).resolve().parents[2]


def policy():
    return json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text(encoding='utf-8'))['claim_review']


def source(key, text, requested=False, path='app.py'):
    return {'id': key, 'path': path, 'excerpt': text, 'sha256': '0'*64,
            'authority': 'documentation_claims' if path == 'README.md' else 'source_excerpt',
            'requested': requested, 'truncated': False}


def test_long_requested_workflow_keeps_middle_conditions_and_tail():
    code = 'def workflow(x):\n' + '    x += 1\n' * 200
    code += '    if x < 3:\n        return "REJECT_CONDITION"\n'
    code += '    x -= 1\n' * 200 + '    return "ACCEPT_TAIL"\n'
    rows = [source('x1', code, True), source('x2', '# public declaration\n'*90, True, 'README.md')]
    rows += [source(f's{i}', 'def tiny():\n    return 1\n'*160, path=f'unit{i}.py') for i in range(20)]
    result = review_context({'root': '.', 'sources': rows},
                            [{'id': 'purpose', 'text': 'Runs a workflow.', 'evidence_ids': ['s1']}], policy())
    found = {r['id']: r for r in result['evidence']['sources']}
    assert found['x1']['excerpt'] == code and found['x1']['supplied_excerpt_preserved']
    assert found['x2']['excerpt'] == rows[1]['excerpt']
    assert result['context_characters'] <= 32000


def test_escaping_and_competing_requests_cannot_overrun_total_budget():
    rows = [source(f'x{i}', ('"\\\nЖ' * 1700), True, f'app{i}.py') for i in range(3)]
    result = review_context({'root': '.', 'sources': rows}, [], policy())
    view = result['evidence']['sources']
    assert result['context_characters'] <= 32000
    assert len(json.dumps({k: result[k] for k in ('evidence', 'claim_packets')}, ensure_ascii=False)) <= 32000
    assert any(r['truncated'] for r in view)
    for before, after in zip(rows, view):
        assert after['supplied_excerpt_preserved'] == (before['excerpt'] == after['excerpt'])


def test_fetched_abbreviation_is_not_mislabelled_complete_source():
    row = source('x1', 'def work():\n    ...\n', True)
    row['truncated'] = True
    result = review_context({'root': '.', 'sources': [row]}, [], policy())['evidence']['sources'][0]
    assert result['supplied_excerpt_preserved'] is True and result['truncated'] is True


def test_advertised_review_catalog_contains_only_supported_reads(tmp_path):
    for name, text in {'app.py': 'def f(): return 1\n', 'README.md': '# API\n',
                       'pyproject.toml': '[project]\nname="app"\n', 'setup.sh': 'echo hi\n',
                       'package.json': '{}\n'}.items():
        (tmp_path / name).write_text(text, encoding='utf-8')
    evidence = run({'project_root': str(tmp_path)})['evidence']
    full = {r['path']: r for r in evidence['source_catalog']}
    context = review_context(evidence, [], policy())['evidence']
    assert {r['path'] for r in context['source_catalog']} == {'app.py', 'README.md'}
    for item in context['source_catalog']:
        output = run({'project_root': str(tmp_path), 'action': 'read',
                      'requests': [{'path': item['path'], 'sha256': full[item['path']]['sha256']}]})
        assert output['evidence']['sources'][0]['requested']


def test_duplicate_lookup_sections_share_only_guaranteed_visible_bytes(tmp_path):
    path = tmp_path / 'app.py'
    path.write_text('def dispatch(x):\n    return worker(x)\n'
                    'def worker(x):\n' + '    x += 1\n'*350 + '    return x\n', encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    collection = json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text(encoding='utf-8'))['collection']
    rows = read_requests(tmp_path, [{'path': 'app.py', 'sha256': digest, 'symbol': symbol}
                                    for symbol in ('dispatch', 'worker')], collection)
    rows.append(source('x3', 'def other():\n' + '    x = 1\n'*400, True, 'other.py'))
    result = review_context({'root': str(tmp_path), 'sources': rows}, [], policy())
    first, alias, other = result['evidence']['sources']
    assert first['excerpt'] == rows[0]['excerpt']
    assert alias['covered_by'] == first['id'] and alias['excerpt'] == ''
    assert other['excerpt'] == rows[2]['excerpt']
    rows[1]['sha256'] = 'f'*64
    changed = review_context({'root': str(tmp_path), 'sources': rows}, [], policy())
    assert changed['evidence']['sources'][1]['covered_by'] == ''
    assert changed['evidence']['sources'][1]['excerpt']
