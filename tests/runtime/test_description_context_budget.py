"""Budget regressions use invented projects, never domain-specific production hints."""
import json
from pathlib import Path

from plugins.project_description.src.evidence import collect
from plugins.project_description.src.excerpts import excerpts


def test_small_budget_keeps_late_function_and_its_condition():
    text = '# header\n' * 300 + '\n'.join(
        f'def worker_{i}(value):\n    if value is None:\n        return "branch_{i}"\n    return value\n'
        for i in range(8))
    result, truncated = excerpts(text, '.py', 2200)
    assert truncated and len(result) <= 2200
    assert all(f'worker_{i}' in result for i in range(8))
    assert 'branch_7' in result


def test_imported_implementation_gets_context_without_domain_hints(tmp_path):
    (tmp_path / 'app.py').write_text('from worker import operate\noperate(None)\n')
    text = '\n'.join(f'def helper_{i}():\n    return "' + 'x' * 350 + '"\n' for i in range(8))
    text += ('def operate(value):\n    if value is None:\n'
             '        return "LOCAL_PATH"\n    return "REMOTE_PATH"\n')
    (tmp_path / 'worker.py').write_text(text)
    policy_path = Path(__file__).resolve().parents[2] / 'plugins/project_description/knowledge/description_policy.json'
    policy = json.loads(policy_path.read_text(encoding='utf-8'))['collection']
    policy.update(max_total_characters=5000, max_file_characters=1800)
    result = collect(tmp_path, policy)
    worker = next(s for s in result['sources'] if s['path'] == 'worker.py')
    assert worker['imported_symbols'] == ['operate']
    assert 'if value is None:' in worker['excerpt']
    assert 'LOCAL_PATH' in worker['excerpt'] and 'REMOTE_PATH' in worker['excerpt']
    assert sum(len(s['excerpt']) for s in result['sources']) <= 5000


def test_tiny_budget_and_nested_definitions_are_bounded():
    text = 'class Worker:\n    def work(self):\n        def inner():\n            return 1\n        return inner()\n' * 20
    for budget in (20, 100, 500, 1600):
        result, truncated = excerpts(text, '.py', budget)
        assert truncated and len(result) <= budget


def test_prioritized_function_does_not_expose_literal_credentials():
    text = '# header\n' * 500 + 'def operate():\n    token = "SECRET_CANARY"\n    return token\n'
    result, _ = excerpts(text, '.py', 1200, focus_symbols=['operate'])
    assert 'SECRET_CANARY' not in result
    assert 'operate' in result


def test_imported_bodies_cannot_spend_reserved_supporting_file_budget(tmp_path):
    (tmp_path / 'app.py').write_text('from first import work\nwork()\n')
    (tmp_path / 'first.py').write_text('from second import work\nwork()\n')
    (tmp_path / 'second.py').write_text('def work():\n' + '    process()\n' * 500)
    (tmp_path / 'view.html').write_text('<button>Independent workflow</button>')
    policy_path = Path(__file__).resolve().parents[2] / 'plugins/project_description/knowledge/description_policy.json'
    policy = json.loads(policy_path.read_text(encoding='utf-8'))['collection']
    policy.update(max_total_characters=6000, max_files=4)
    result = collect(tmp_path, policy)
    assert {s['path'] for s in result['sources']} == {'app.py', 'first.py', 'second.py', 'view.html'}
    assert sum(len(s['excerpt']) for s in result['sources']) <= 6000
