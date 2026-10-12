"""Compiled-competency route: model-free goal delivery through native red/green gates."""
import sys
from pathlib import Path

from runtime.feature_competency import run_competency_first, task_competencies

UNPICKLABLE = '''class FetchError(Exception):
    def __init__(self, url, status):
        self.url = url
        self.status = status
        super().__init__(f"{url} failed with {status}")
'''
PICKLABLE = '''class FetchError(Exception):
    def __init__(self, url, status):
        self.url = url
        self.status = status
        super().__init__(url, status)
'''
REGRESSION = '''from pkg.errors import FetchError


def test_message():
    assert str(FetchError("u", 5)) == "u failed with 5"
'''


def _project(tmp_path, errors=UNPICKLABLE, regression=REGRESSION):
    root = tmp_path / 'project'
    (root / 'src/pkg').mkdir(parents=True)
    (root / 'tests').mkdir()
    (root / 'src/pkg/__init__.py').write_text('', encoding='utf-8')
    (root / 'src/pkg/errors.py').write_text(errors, encoding='utf-8')
    (root / 'tests/test_errors.py').write_text(regression, encoding='utf-8')
    return root


def test_catalog_lists_registered_task_competencies():
    assert [r['capability'] for r in task_competencies()] == ['exception_pickle', 'learned_fix_templates']


def test_pickle_goal_is_delivered_without_model_calls(tmp_path):
    project = _project(tmp_path)
    report = run_competency_first(project=project, work=tmp_path / 'work', python=Path(sys.executable),
                                  goal='Make FetchError picklable so workers can return it')
    assert report['status'] == 'verified', report.get('reason')
    assert report['model_calls'] == 0 and report['source_apply'] is False
    assert report['baseline']['counts']['failed'] == 1 and report['candidate']['counts']['passed'] == 1
    assert report['regression_scope'] == ['tests/test_errors.py'] and report['regression']['changed'] == []
    assert (project / 'src/pkg/errors.py').read_text(encoding='utf-8') == UNPICKLABLE


def test_apply_source_installs_verified_change(tmp_path):
    project = _project(tmp_path)
    report = run_competency_first(project=project, work=tmp_path / 'work', python=Path(sys.executable),
                                  goal='FetchError must survive pickle', apply_source=True)
    assert report['status'] == 'installed'
    assert '__reduce__' in (project / 'src/pkg/errors.py').read_text(encoding='utf-8')
    assert (project / 'tests/test_cos_pickle_fetch_error.py').is_file()


def test_unrelated_goal_is_refused_before_any_execution(tmp_path):
    report = run_competency_first(project=_project(tmp_path), work=tmp_path / 'work',
                                  python=Path(sys.executable), goal='Add retry with backoff to the client')
    assert report['status'] == 'not_applicable'
    assert report['attempts'] == [{'competency': 'exception_pickle', 'status': 'not_applicable',
                                   'reason': 'goal_does_not_request_pickle_support'},
                                  {'competency': 'learned_fix_templates', 'status': 'not_applicable',
                                   'reason': 'goal_does_not_request_a_learned_rule'}]
    assert 'baseline' not in report


def test_already_picklable_class_is_not_a_candidate(tmp_path):
    report = run_competency_first(project=_project(tmp_path, errors=PICKLABLE), work=tmp_path / 'work',
                                  python=Path(sys.executable), goal='Make FetchError picklable')
    assert report['status'] == 'not_applicable'
    assert report['attempts'][0]['reason'] == 'no_supported_unpicklable_exception_in_sources'


def test_changed_regression_outcome_blocks_delivery(tmp_path):
    guard = REGRESSION + '''

def test_no_custom_reduce():
    assert '__reduce__' not in FetchError.__dict__
'''
    project = _project(tmp_path, regression=guard)
    report = run_competency_first(project=project, work=tmp_path / 'work', python=Path(sys.executable),
                                  goal='Make FetchError picklable', apply_source=True)
    assert report['status'] == 'blocked' and report['reason'] == 'competency_regression_outcome_changed'
    assert any(name.endswith('test_no_custom_reduce') for name in report['regression']['changed'])
    assert (project / 'src/pkg/errors.py').read_text(encoding='utf-8') == UNPICKLABLE
