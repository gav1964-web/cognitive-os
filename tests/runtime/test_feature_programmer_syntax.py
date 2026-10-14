"""A real syntax failure returns to Programmer, preserving native/review gates."""
import json
import pytest

from runtime.feature_workspace import inventory
from runtime.feature_acceptance import save
from runtime.feature_programmer_syntax import restored_feedback
from runtime.feature_quality_resume import restore_qualified_spec
from runtime.feature_quality_chat import QualityChat
from tests.runtime.test_feature_development import project, fake_chat, run


@pytest.mark.parametrize('corrected', [True, False])
def test_syntax_correction_is_model_owned_and_bounded(project, tmp_path, corrected):
    delegate = fake_chat(project); calls = []
    def chat(messages, *, config):
        result = delegate(messages, config=config)
        if config.provider_label == 'feature:programmer':
            calls.append(json.loads(messages[1]['content']))
            if len(calls) == 1 or not corrected:
                result['edits'][0]['replacements'][0]['new'] = 'return ('
            else:
                feedback = calls[-1]['feedback']
                assert feedback['syntax_error']['line'] == 2
                assert feedback['rejected_proposal']['edits'][0]['replacements'][0]['new'] == 'return ('
        return result
    before = inventory(project)
    result = run(project, tmp_path, chat=chat)
    assert len(calls) == 2 and inventory(project) == before
    if corrected:
        assert result['status'] == 'verified'
        assert result['attempts'][0]['counts']['passed'] == 2
        assert result['artifacts']['reviewer']['decision'] == 'approve'
    else:
        assert result['reason'] == 'feature_edit_syntax_correction_exhausted'
        assert not result['attempts'] and 'reviewer' not in result['artifacts']
        q = QualityChat(None, tmp_path / 'quality')
        restore_qualified_spec(q, tmp_path / 'run', project, before, result['goal'])
        assert q.frozen and not q.retained
        feedback = restored_feedback(tmp_path / 'run', project, before,
            {t['path']: t['content'].encode() for t in q.frozen}, ['engine.py'])
        assert feedback['syntax_error']['line'] == 2
        proposal = delegate([], config=type('Config', (), {'provider_label': 'feature:programmer'})())
        save(tmp_path / 'run/proposal-1.json', proposal)
        with pytest.raises(ValueError, match='syntax_resume_not_reproduced'):
            restore_qualified_spec(q, tmp_path / 'run', project, before, result['goal'])
