from pathlib import Path

from evaluation.acceptance.check_uppercase_cli import check_project
from runtime.llm_sandbox_implementation import run_llm_sandbox_implementation


def test_generated_cli_satisfies_external_frozen_file_contract(tmp_path):
    report = run_llm_sandbox_implementation(root=tmp_path,
        prompt='Напиши CLI .py, которая переводит текстовый файл в верхний регистр.', write=True)
    project = Path(report['project_dir'])
    assert report['status'] == 'sandbox_verified'
    assert 'main.py' in report['files']
    result = check_project(project)
    assert result['status'] == 'passed', result


def test_deep_output_path_does_not_require_long_bytecode_cache_names(tmp_path):
    output = tmp_path / ('x' * max(1, 175 - len(str(tmp_path))))
    report = run_llm_sandbox_implementation(root=tmp_path,
        prompt='Напиши CLI: прочитай stdin, переведи текст в нижний регистр и сохрани результат в файл',
        output_dir=output, write=True)
    assert report['verification']['compile']['status'] == 'passed', report['verification']
    assert report['status'] == 'sandbox_verified', report['verification']
