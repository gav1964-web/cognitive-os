import hashlib

import pytest

from runtime.evaluation_input_snapshot import copy_input_snapshot


def test_selected_copy_is_exact_and_source_unchanged(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.py').write_bytes(b'print(42)\r\n')
    (source / 'config.json').write_text('private')
    result = copy_input_snapshot(source, tmp_path / 'copy', ['main.py'])
    assert result['source_sha256']['main.py'] == hashlib.sha256(b'print(42)\r\n').hexdigest()
    assert (tmp_path / 'copy/main.py').read_bytes() == (source / 'main.py').read_bytes()
    assert not (tmp_path / 'copy/config.json').exists()
    with pytest.raises(ValueError, match='destination_exists'):
        copy_input_snapshot(source, tmp_path / 'copy', ['main.py'])


@pytest.mark.parametrize('name', ['config.json', '.env.example', '../outside', '.git/index', 'x:stream', 'C:/a'])
def test_private_or_external_selection_never_reads_contents(tmp_path, monkeypatch, name):
    def forbidden(*args, **kwargs):
        pytest.fail('must reject before opening')
    monkeypatch.setattr('pathlib.Path.open', forbidden)
    with pytest.raises(ValueError):
        copy_input_snapshot(tmp_path, tmp_path / 'copy', [name])
    assert not (tmp_path / 'copy').exists()


def test_link_cannot_enter_snapshot(tmp_path):
    target = tmp_path / 'real.py'
    target.write_text('pass')
    try:
        (tmp_path / 'linked.py').symlink_to(target)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    with pytest.raises(ValueError, match='linked'):
        copy_input_snapshot(tmp_path, tmp_path / 'copy', ['linked.py'])
