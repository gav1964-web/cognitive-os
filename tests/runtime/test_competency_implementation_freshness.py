"""Declared package identity must cover already imported dependency code."""
import json
import shutil
import uuid

import pytest

from runtime.competency_knowledge import invoke_knowledge
from tests.runtime.test_competency_knowledge import provider, _register


@pytest.mark.parametrize('second_entrypoint', [False, True])
def test_changed_dependency_requires_restart_even_after_registration(provider, monkeypatch, second_entrypoint):
    root, name, directory = provider
    package = 'test_impl_' + uuid.uuid4().hex[:12]
    module = root / package / '__init__.py'
    module.parent.mkdir()
    module.write_text("VALUE = 'first'\n", encoding='utf-8')
    monkeypatch.syspath_prepend(str(root))
    manifest = directory / 'plugin.json'
    data = json.loads(manifest.read_text())
    data['implementation_packages'] = [package]
    manifest.write_text(json.dumps(data), encoding='utf-8')
    main = directory / 'src/main.py'
    source = main.read_text(encoding='utf-8')
    source = f'from {package} import VALUE\n' + source.replace("    if payload['operation']", "    record['dependency_value'] = VALUE\n    if payload['operation']")
    main.write_text(source, encoding='utf-8')
    _register(root, name)
    assert invoke_knowledge(name, {'operation':'boundary_profiles'}, root=root)['records'][0]['dependency_value'] == 'first'
    module.write_text("VALUE = 'second-version'\n", encoding='utf-8')
    with pytest.raises(ValueError, match='identity_mismatch'):
        invoke_knowledge(name, {'operation':'boundary_profiles'}, root=root)
    if second_entrypoint:
        other = name + '_other'
        destination = directory.with_name(other)
        shutil.copytree(directory, destination)
        data.update(id=other, entrypoint=f'plugins.{other}.src.main:run')
        (destination / 'plugin.json').write_text(json.dumps(data), encoding='utf-8')
        name = other
    _register(root, name)
    with pytest.raises(ValueError, match='code_changed_restart_required'):
        invoke_knowledge(name, {'operation':'boundary_profiles'}, root=root)
