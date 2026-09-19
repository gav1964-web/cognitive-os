import json
from pathlib import Path

import pytest

from runtime.stage_finalization import audit_stage, finalize_stage
from runtime.stage_finalization_workspace import inventory, apply_verified


def project(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    functions = []
    for name in ('first', 'second', 'third'):
        functions.append(f'''def {name}(value):
    """Return an explicitly bounded normalized value."""
    value = value.strip()
    if not value:
        return "empty"
    value = value.lower()
    return value
''')
    (root / 'sample.py').write_text('\n'.join(functions))
    tests = root / 'tests'
    tests.mkdir()
    (tests / 'test_sample.py').write_text('''import pickle
import sample

def test_behavior_and_public_identity():
    for name in ("first", "second", "third"):
        function = getattr(sample, name)
        assert function(" HELLO ") == "hello"
        assert function(" ") == "empty"
        assert function.__module__ == "sample"
        assert pickle.loads(pickle.dumps(function)) is function
''')
    return root


def planner(task):
    return {'source_sha256': task['sha256'], 'groups': [
        {'module': 'text_normalization', 'reason': 'Normalize names with identical empty-value behavior.',
         'functions': ['first', 'second']}]}, [{'model': 'test-double', 'total_tokens': 0}]


def test_development_warns_but_final_stage_blocks(tmp_path):
    root = project(tmp_path)
    development = audit_stage(root, phase='development', max_lines=20)
    final = audit_stage(root, max_lines=20)
    assert development['blocking'] is False and development['stage_complete'] is False
    assert final['blocking'] is True
    assert development['tasks'][0]['candidates']


@pytest.mark.parametrize('apply', [False, True])
def test_full_baseline_plan_patch_verification_and_optional_apply(tmp_path, apply):
    root = project(tmp_path)
    before = inventory(root)
    result = finalize_stage(root, repair=True, apply=apply, max_lines=20, test_targets=['tests'],
                            planner=planner, work_root=tmp_path / 'work')
    assert result['status'] == ('completed' if apply else 'verified_patch'), result
    assert result['source_applied'] is apply
    assert result['baseline']['passing'] == result['verification']['passing'] == 1
    assert all(result['checks'].values())
    if apply:
        assert (root / 'text_normalization.py').is_file()
        assert audit_stage(root, max_lines=20)['stage_complete']
    else:
        assert inventory(root) == before
    assert 'source' not in result['tasks'][0]['candidates'][0]


def test_missing_test_scope_never_calls_model(tmp_path):
    root = project(tmp_path)
    def forbidden(_task):
        raise AssertionError('Model must not run without regression scope')
    result = finalize_stage(root, repair=True, max_lines=20, planner=forbidden)
    assert result['reason'] == 'explicit_regression_scope_required'


def test_clean_stage_does_not_call_model_or_apply(tmp_path):
    root = project(tmp_path)
    result = finalize_stage(root, repair=True, apply=True, planner=lambda _: pytest.fail('unnecessary LLM'))
    assert result['status'] == 'completed' and result['source_applied'] is False


def test_bad_baseline_blocks_before_planning(tmp_path):
    root = project(tmp_path)
    (root / 'tests/test_sample.py').write_text('def test_failure():\n    assert False\n')
    result = finalize_stage(root, repair=True, max_lines=20, test_targets=['tests'],
                            planner=lambda _: pytest.fail('bad baseline'), work_root=tmp_path / 'work')
    assert result['reason'] == 'baseline_verification_failed'
    assert not (root / 'text_normalization.py').exists()


def test_invalid_model_response_does_not_mutate_source(tmp_path):
    root = project(tmp_path)
    before = inventory(root)
    result = finalize_stage(root, repair=True, apply=True, max_lines=20, test_targets=['tests'],
        planner=lambda task: ({'source_sha256': task['sha256'], 'groups': [], 'commands': ['evil']}, []),
        work_root=tmp_path / 'work')
    assert result['status'] == 'needs_replanning'
    assert inventory(root) == before


def test_transaction_rejects_intervening_edits(tmp_path):
    root = project(tmp_path)
    before = inventory(root)
    (root / 'sample.py').write_text('changed_by_user = True\n')
    with pytest.raises(ValueError, match='source_changed'):
        apply_verified(root, before, {'sample.py': b'pass\n'})
    assert (root / 'sample.py').read_text() == 'changed_by_user = True\n'
    assert not (root / '.stage-finalization.lock').exists()


def test_snapshot_omits_local_secrets_and_generated_artifacts(tmp_path):
    root = project(tmp_path)
    (root / 'config.json').write_text('private')
    (root / '.env').write_text('private')
    (root / 'artifacts').mkdir()
    (root / 'artifacts/data.py').write_text('generated')
    assert not {'config.json', '.env', 'artifacts/data.py'} & inventory(root).keys()


def test_changed_test_outcome_prevents_application(tmp_path):
    root = project(tmp_path)
    test = root / 'tests/test_sample.py'
    with test.open('a') as stream:
        stream.write('\ndef test_source_location_contract():\n    assert sample.first.__code__.co_filename.endswith("sample.py")\n')
    before = inventory(root)
    result = finalize_stage(root, repair=True, apply=True, max_lines=20, test_targets=['tests'],
                            planner=planner, work_root=tmp_path / 'work')
    assert result['baseline']['status'] == 'passed'
    assert result['verification']['status'] == 'failed'
    assert result['source_applied'] is False and inventory(root) == before


def test_llm_failure_has_a_receipt_without_provider_body(tmp_path):
    from runtime.local_inference import LocalInferenceError
    root = project(tmp_path)
    def unavailable(_):
        raise LocalInferenceError('provider echoed secret-token')
    result = finalize_stage(root, repair=True, max_lines=20, test_targets=['tests'],
                            planner=unavailable, work_root=tmp_path / 'work')
    assert result['reason'] == 'llm_unavailable_or_invalid_response'
    encoded = (Path(result['work_directory']) / 'report.json').read_text(encoding='utf-8')
    assert 'secret-token' not in encoded


def test_transaction_rolls_back_a_partial_write(tmp_path, monkeypatch):
    from runtime import stage_finalization_workspace as workspace
    root = project(tmp_path)
    before = inventory(root)
    original_write = workspace._atomic_write
    calls = []
    def fail_second(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise OSError('simulated write failure')
        original_write(path, data)
    monkeypatch.setattr(workspace, '_atomic_write', fail_second)
    with pytest.raises(OSError):
        workspace.apply_verified(root, before, {'sample.py': b'changed = True\n', 'added.py': b'pass\n'})
    assert inventory(root) == before


def test_no_tests_collected_cannot_validate_a_patch(tmp_path):
    root = project(tmp_path)
    (root / 'tests/test_sample.py').write_text('# no tests\n')
    result = finalize_stage(root, repair=True, max_lines=20, test_targets=['tests'],
                            planner=planner, work_root=tmp_path / 'work')
    assert result['reason'] == 'baseline_verification_failed'
