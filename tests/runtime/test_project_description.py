"""Product description evidence, refusal boundaries and transparent model input."""
import json
from pathlib import Path

import pytest

from plugins.project_description.src.main import run
from plugins.project_description.src.evidence import collect
from plugins.project_description.src.excerpts import excerpts
from plugins.project_description.src.surface import source_surface
from runtime import project_description as description
from runtime.local_inference import LocalInferenceError

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'README.md').write_text('# Ledger\nSummarize invoice CSV files as monthly totals.', encoding='utf-8')
    (tmp_path / 'app.py').write_text('def summarize(rows):\n    return sum(rows)\n', encoding='utf-8')
    return tmp_path


def _answer():
    claim = {'text': 'Summarizes invoice CSV files.', 'evidence_ids': ['s1']}
    return {'purpose': claim, 'scenarios': [dict(claim)], 'data_flow': [dict(claim)],
            'unknowns': [], 'confidence': 'medium'}


def _review_or_draft(messages, answer):
    if 'draft' in json.loads(messages[1]['content']):
        return {'description': answer, 'corrections': [], 'claim_reviews': [
            {'claim_id': row['id'], 'action': 'retained', 'reason': 'Supported by fixture.',
             'evidence_ids': row['evidence_ids']}
            for row in json.loads(messages[1]['content'])['draft_claims']]}
    return answer


def test_source_selection_deduplicates_without_project_specific_folder_names(project):
    (project / 'release_copy').mkdir()
    (project / 'release_copy/app.py').write_bytes((project / 'app.py').read_bytes())
    (project / '.env').write_text('PRIVATE_ENV_CANARY', encoding='utf-8')
    (project / 'config.json').write_text('PRIVATE_CONFIG_CANARY', encoding='utf-8')
    (project / 'catalog_snippets.txt').write_text('ADVERTISING_CANARY', encoding='utf-8')
    result = run({'project_root': str(project)})
    serialized = json.dumps(result)
    assert 'PRIVATE_ENV_CANARY' not in serialized
    assert 'PRIVATE_CONFIG_CANARY' not in serialized
    assert 'ADVERTISING_CANARY' not in serialized
    evidence = result['evidence']
    assert evidence['sources'][0]['path'] == 'app.py'
    assert evidence['duplicates'] == [{'path': 'release_copy/app.py', 'same_bytes_as': 'app.py'}]
    assert {r['path'] for r in evidence['sources']} == {'README.md', 'app.py'}


def test_large_source_keeps_late_fallback_and_interface_text():
    source = ('API_TOKEN = "SECRET_CANARY"\n'
              'def index():\n    return """<html><style>hidden_css</style><button>Import documents</button>'
              + ' ' * 60000 + '</html>"""\n'
              'def import_documents(model):\n    if model is None:\n        return parse_rules()\n    return model.extract()\n')
    result, truncated = excerpts(source, '.py', 10000)
    assert truncated and len(result) <= 10000
    assert 'import_documents' in result and 'parse_rules()' in result
    assert 'Import documents' in result
    assert 'SECRET_CANARY' not in result


@pytest.mark.parametrize('pattern', ['*.rtf', '*.csv', '*.wav'])
def test_input_glob_in_middle_of_long_entrypoint_survives(pattern):
    source = ('def main():\n' + '    value = 1\n' * 800
              + f'    for path in documents.glob("{pattern}"):\n        parse(path)\n'
              + '    value = 2\n' * 800)
    result, truncated = excerpts(source, '.py', 10000)
    assert truncated
    assert f'documents.glob("{pattern}")' in result


def test_embedded_html_compaction_retains_entire_python_control_flow():
    source = ('def index():\n    return "<html>' + ' ' * 60000 + '</html>"\n'
              'def main(model):\n    if model is None:\n        return parse_rules()\n'
              '    for path in documents.glob("*.rtf"):\n        model.parse(path)\n')
    result, truncated = excerpts(source, '.py', 5000)
    assert truncated and len(result) <= 5000
    assert 'if model is None:' in result and 'return parse_rules()' in result
    assert "documents.glob('*.rtf')" in result and 'model.parse(path)' in result


def test_readme_setup_claims_are_not_source_facts(project):
    (project / 'README.md').write_text('# Product\nA useful tool.\n## Setup\nUnverified format support.', encoding='utf-8')
    evidence = run({'project_root': str(project)})['evidence']
    doc = next(s for s in evidence['sources'] if s['path']=='README.md')
    assert doc['authority'] == 'documentation_claims' and doc['truncated']
    assert 'A useful tool.' in doc['excerpt']
    assert 'Unverified format support.' not in doc['excerpt']


def test_surface_index_preserves_routes_formats_and_controls():
    text = ('@app.route("/unresolved")\ndef page():\n'
            '    return "<html><button>Unresolved records</button></html>"\n'
            'def main():\n    return documents.glob("*.csv")\n')
    result = source_surface(text, '.py')
    assert result['route_literals'] == ['/unresolved']
    assert result['file_glob_literals'] == ['*.csv']
    assert result['visible_ui_text'] == ['Unresolved records']


def test_owner_statement_is_rendered_even_if_model_omits_it(project):
    result = description.describe_project(project, owner_notes=['Import works without a model.'],
                                         chat=lambda messages, **kwargs: _review_or_draft(messages, _answer()))
    assert result['status'] == 'described'
    assert 'Import works without a model.' in description.render_description(result)


def test_model_cannot_rewrite_owner_statement(project):
    def chat(messages, **kwargs):
        answer = _answer()
        answer['scenarios'] = [{'text': 'A model is required.', 'evidence_ids': ['owner1']}]
        return _review_or_draft(messages, answer)
    result = description.describe_project(project, owner_notes=['Import works without a model.'], chat=chat)
    assert result['reason'] == 'description_unknown_evidence'
    assert result['description'] is None


def test_description_model_profile_has_independent_default(monkeypatch):
    monkeypatch.delenv('COGNITIVE_OS_DESCRIPTION_MODEL', raising=False)
    monkeypatch.delenv('COGNITIVE_OS_L45_MODEL', raising=False)
    assert description.description_model_config().model == 'deepseek/deepseek-v3.2'
    assert description.LocalInferenceConfig.from_l45_env().model == 'deepseek/deepseek-chat'
    monkeypatch.setenv('COGNITIVE_OS_DESCRIPTION_MODEL', 'explicit-model')
    assert description.description_model_config().model == 'explicit-model'


def test_file_execution_is_never_needed(project):
    (project / 'app.py').write_text('raise RuntimeError("must not execute")\n', encoding='utf-8')
    assert run({'project_root': str(project)})['status'] == 'ok'


def test_archived_html_does_not_displace_source_or_readme(project):
    (project / 'downloaded_page.html').write_text('<p>advertisement</p>' * 6000, encoding='utf-8')
    rows = run({'project_root': str(project)})['evidence']['sources']
    assert [row['path'] for row in rows[:2]] == ['app.py', 'README.md']


def test_collection_limits_are_explicit(project):
    policy = json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text())['collection']
    result = collect(project, {**policy, 'max_files': 1})
    assert len(result['sources']) == 1
    assert result['omitted'] == [{'path': 'README.md', 'reason': 'context_budget'}]


def test_src_application_is_not_displaced_by_many_shallow_tools(tmp_path):
    package = tmp_path / 'src' / 'ledger'
    package.mkdir(parents=True)
    (package / 'server.py').write_text('def serve(): return "APPLICATION_CANARY"', encoding='utf-8')
    (package / 'totals.py').write_text('def total(rows): return sum(rows)', encoding='utf-8')
    (tmp_path / 'README.md').write_text('# Ledger\nInvoice totals.', encoding='utf-8')
    (tmp_path / 'tools').mkdir()
    for index in range(35):
        (tmp_path / 'tools' / f'audit{index}.py').write_text(f'def audit(): return {index}', encoding='utf-8')
    policy = json.loads((ROOT / 'plugins/project_description/knowledge/description_policy.json').read_text())['collection']
    result = collect(tmp_path, {**policy, 'max_files': 3})
    assert [row['path'] for row in result['sources']] == [
        'src/ledger/server.py', 'README.md', 'src/ledger/totals.py']
    assert result['sources'][0]['primary']
    assert 'APPLICATION_CANARY' in result['sources'][0]['excerpt']


def test_no_map_domain_is_injected_into_unrelated_cli():
    result = run({'project_root': str(ROOT / 'tests/fixtures/project_description/invoice_cli')})
    text = json.dumps(result, ensure_ascii=False)
    assert 'Invoice totals' in text and 'Decimal' in text
    assert 'Leaflet' not in text and 'Курск' not in text and 'async_worker' not in text


def test_project_domain_changes_evidence_not_instructions(tmp_path):
    instructions = []
    for name, source in [('map', 'def render_layers(): return "GEOGRAPHIC_CANARY"'),
                         ('VR', 'def play_audio(): return "AUDIO_CANARY"'),
                         ('ledger', 'def sum_invoices(): return "LEDGER_CANARY"')]:
        root = tmp_path / name
        root.mkdir()
        (root / 'main.py').write_text(source, encoding='utf-8')
        result = run({'project_root': str(root)})
        assert source in result['evidence']['sources'][0]['excerpt']
        pair = (result['instruction'], result['review_instruction'])
        assert all('CANARY' not in item for item in pair)
        instructions.append(pair)
    assert instructions[0] == instructions[1] == instructions[2]
    # Known regressions are evaluation data, not a checklist injected into prompts.
    for instruction in instructions[0]:
        assert not any(hint in instruction.lower() for hint in (
            'geographic', 'display layers', 'unresolved records', 'import progress',
            'offline viewing', 'single-user', 'docx', 'rtf'))


def test_registered_route_preserves_owner_authority_and_citations(project):
    captured = []

    def chat(messages, **kwargs):
        captured.extend(messages)
        result = _answer()
        return _review_or_draft(messages, result)

    result = description.describe_project(project, chat=chat, owner_notes=['Rule fallback is less accurate.'])
    assert result['status'] == 'described'
    payload = json.loads(captured[1]['content'])
    assert 'owner_notes' not in payload
    assert result['owner_notes'][0]['authority'] == 'owner_statement'
    assert 'async_worker' not in captured[1]['content']
    assert result['verification']['semantic_review_required']
    assert 'Rule fallback is less accurate.' in description.render_description(result)
    assert result['source_application'] is False


@pytest.mark.parametrize('mutation', ['missing', 'invented_ref', 'empty_ref', 'confidence_type'])
def test_malformed_model_claims_are_not_published(project, mutation):
    def chat(*args, **kwargs):
        result = _answer()
        if mutation == 'missing':
            del result['data_flow']
        elif mutation == 'confidence_type':
            result['confidence'] = []
        else:
            result['purpose']['evidence_ids'] = ['unseen.py'] if mutation == 'invented_ref' else []
        return result
    result = description.describe_project(project, chat=chat)
    assert result['status'] == 'failed' and result['description'] is None


def test_source_change_during_model_request_prevents_publication(project):
    def chat(messages, **kwargs):
        (project / 'app.py').write_text('# concurrent change\n', encoding='utf-8')
        return _review_or_draft(messages, _answer())
    result = description.describe_project(project, chat=chat)
    assert result['reason'] == 'description_source_changed_during_request'
    assert result['description'] is None


def test_provider_failure_is_not_an_invented_description(project):
    def chat(*args, **kwargs):
        raise LocalInferenceError('provider_unavailable')
    result = description.describe_project(project, chat=chat)
    assert result['status'] == 'failed'
    assert result['description'] is None
    assert 'provider_unavailable' in description.render_description(result)


def test_failed_review_does_not_publish_the_draft(project):
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 2:
            raise LocalInferenceError('review_unavailable')
        return _answer()
    result = description.describe_project(project, chat=chat)
    assert len(calls) == 2 and result['status'] == 'failed'
    assert result['description'] is None and result['raw_response'] == _answer()


def test_review_can_correct_draft_but_cannot_invent_references(project):
    def chat(messages, **kwargs):
        if 'draft' not in json.loads(messages[1]['content']):
            return _answer()
        revised = _answer()
        revised['purpose']['evidence_ids'] = ['nonexistent']
        return {**_review_or_draft(messages, revised), 'corrections': ['corrected purpose']}
    result = description.describe_project(project, chat=chat)
    assert result['reason'] == 'description_unknown_evidence'
    assert result['description'] is None


def test_plugin_registration_is_required(project, monkeypatch):
    def denied(*args, **kwargs):
        raise ValueError('knowledge_provider_not_active')
    monkeypatch.setattr(description, 'invoke_knowledge', denied)
    with pytest.raises(ValueError, match='not_active'):
        description.describe_project(project, chat=lambda *a, **k: pytest.fail('must not call model'))
