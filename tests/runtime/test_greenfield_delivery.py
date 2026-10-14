import copy
from pathlib import Path

import pytest

from runtime.greenfield_delivery import run_greenfield_delivery
from runtime.greenfield_delivery_contracts import bind_implementation
from runtime.evaluation_route_execution import verify_task15
from runtime.role_pipeline import run_role_pipeline

PROMPT = 'Напиши CLI .py, которая переводит текстовый файл в верхний регистр.'


def plan(tmp_path, prompt=PROMPT):
    return run_greenfield_delivery(root=tmp_path, project_dir=tmp_path / 'artifacts/output', goal=prompt)


def test_planning_binds_actual_spec_recipe_and_does_not_write(tmp_path):
    result = plan(tmp_path)
    assert result['status'] == 'planned', result
    artifacts = result['artifacts']
    assert artifacts['product_architecture']['pattern_id'] == 'uppercase_file_cli'
    assert artifacts['implementation_handoff']['status'] == 'ready'
    assert artifacts['test_plan']['acceptance_check_ids'] == ['unicode', 'empty', 'crlf', 'invalid_utf8', 'missing', 'same_path']
    assert not (tmp_path / 'artifacts').exists()


def test_pattern_supports_existing_human_document_writer(tmp_path):
    from runtime.greenfield_role_pipeline import run_greenfield_role_pipeline
    result = run_greenfield_role_pipeline(root=tmp_path, prompt=PROMPT, write=True)
    assert result['status'] == 'ok'
    spec = Path(result['human_documents']['product_technical_spec']).read_text(encoding='utf-8')
    assert 'file_to_file_text_transform' in spec


def test_native_greenfield_pipeline_delivers_real_cli_with_external_acceptance(tmp_path):
    output = tmp_path / 'artifacts/output'
    result = run_role_pipeline(root=tmp_path, project_dir=output, goal=PROMPT,
        mode='greenfield', write=True, run_executor=True,
        delivery_verifier=lambda p: verify_task15(p, tmp_path / 'checks'))
    assert result['status'] == 'completed', result
    assert result['artifacts']['review']['status'] == 'approved'
    assert all(result['artifacts']['review']['checks'].values())
    assert result['safety']['llm_invoked'] is False
    assert result['executor'] == 'native_greenfield_bounded_delivery.v1'
    assert Path(result['report_path']).is_file()


@pytest.mark.parametrize('prompt', [
    'напиши программу cli для расчета фазы луны по переданной дате',
    'CLI uppercase: read stdin and write stdout',
])
def test_unsupported_or_conflicting_contract_never_runs_programmer(tmp_path, prompt):
    result = run_greenfield_delivery(root=tmp_path, project_dir=tmp_path / 'artifacts/output',
        goal=prompt, write=True, run_executor=True, verify=lambda p: pytest.fail('unexpected execution'))
    assert result['status'] == 'blocked'
    assert not result['safety']['implementation_started']
    assert not (tmp_path / 'artifacts/output').exists()


def test_existing_output_is_preserved(tmp_path):
    output = tmp_path / 'artifacts/output'
    output.mkdir(parents=True)
    source = output / 'main.py'
    source.write_text('user content')
    with pytest.raises(ValueError, match='empty_output'):
        run_greenfield_delivery(root=tmp_path, project_dir=output, goal=PROMPT, write=True)
    assert source.read_text() == 'user content'


def test_output_cannot_be_maintained_source(tmp_path):
    with pytest.raises(ValueError, match='under_artifacts'):
        run_greenfield_delivery(root=tmp_path, project_dir=tmp_path / 'runtime', goal=PROMPT)


def test_external_verifier_is_mandatory_before_programmer(tmp_path):
    result = run_greenfield_delivery(root=tmp_path, project_dir=tmp_path / 'artifacts/output',
        goal=PROMPT, write=True, run_executor=True)
    assert result['reason'] == 'explicit_write_and_external_verifier_required'
    assert not result['safety']['implementation_started']


def test_spec_cannot_relabel_a_different_operation(tmp_path):
    result = plan(tmp_path)
    spec = copy.deepcopy(result['artifacts']['product_technical_spec'])
    spec['primary_contract']['delivery_recipe']['transform'] = 'lowercase'
    preview = {'status': 'planned', 'implementation_plan': result['artifacts']['implementation_handoff']['implementation_plan']}
    assert bind_implementation(spec, preview)['status'] == 'blocked'


@pytest.mark.parametrize('mode', ['missing_cases', 'failed_case', 'mutated_source', 'exception'])
def test_generated_tests_alone_do_not_bypass_delivery_review(tmp_path, mode):
    def verifier(project):
        if mode == 'exception':
            raise RuntimeError('private error detail')
        checks = [{'id': name, 'passed': True} for name in ['unicode', 'empty', 'crlf', 'invalid_utf8', 'missing', 'same_path']]
        if mode == 'missing_cases':
            checks.pop()
        if mode == 'failed_case':
            checks[0]['passed'] = False
        if mode == 'mutated_source':
            (project / 'main.py').write_text('print("tampered")')
        return {'status': 'passed', 'pytest': {'returncode': 0, 'passing': 1},
                'acceptance': {'status': 'passed', 'checks': checks}}
    result = run_greenfield_delivery(root=tmp_path, project_dir=tmp_path / 'artifacts/output',
        goal=PROMPT, write=True, run_executor=True, verify=verifier)
    assert result['status'] == 'blocked'
    assert result['artifacts']['review']['status'] == 'request_rework'
    assert 'private error detail' not in str(result)
