import json
from pathlib import Path
import pytest

from runtime.feature_target_rollback import rollback_target
from runtime.feature_workspace import install, inventory
from runtime.feature_acceptance import save


def installed(tmp_path):
    project=tmp_path/'project'
    project.mkdir()
    (project/'engine.py').write_bytes(b'old\n')
    before=inventory(project)
    work=tmp_path/'install'
    changes={'engine.py':b'new\n','tests/test_new.py':b'assert 1\n'}
    receipt=install(project,before,changes,work/'backup')
    after=inventory(project)
    save(work/'report.json',{'schema_version':'feature_target_delivery.v1',
        'status':'installed','source_apply':True,'target':str(project),
        'source_hashes':before,'final_hashes':after,'installation':receipt})
    return project,work/'report.json'


def test_plan_and_exact_rollback_preserve_unrelated_local_files(tmp_path):
    project,receipt=installed(tmp_path)
    (project/'local.txt').write_bytes(b'user')
    planned=rollback_target(receipt=receipt,work=tmp_path/'plan')
    assert planned['status']=='planned' and (project/'engine.py').read_bytes()==b'new\n'
    result=rollback_target(receipt=receipt,work=tmp_path/'restore',apply=True)
    assert result['status']=='rolled_back'
    assert (project/'engine.py').read_bytes()==b'old\n'
    assert not (project/'tests/test_new.py').exists()
    assert (project/'local.txt').read_bytes()==b'user'


@pytest.mark.parametrize('tamper',['target','backup'])
def test_stale_content_cannot_be_replaced(tmp_path,tamper):
    project,receipt=installed(tmp_path)
    path=project/'engine.py' if tamper=='target' else receipt.parent/'backup/engine.py'
    path.write_bytes(b'changed')
    before=inventory(project)
    with pytest.raises(ValueError):
        rollback_target(receipt=receipt,work=tmp_path/'restore',apply=True)
    assert inventory(project)==before


def test_failure_restores_installed_candidate(tmp_path,monkeypatch):
    import runtime.feature_target_rollback as module
    project,receipt=installed(tmp_path)
    before=inventory(project)
    original=Path.unlink
    def fail_once(path,*args,**kwargs):
        if path.name=='test_new.py':
            raise OSError('cannot remove')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',fail_once)
    with pytest.raises(OSError,match='cannot remove'):
        rollback_target(receipt=receipt,work=tmp_path/'restore',apply=True)
    assert inventory(project)==before
