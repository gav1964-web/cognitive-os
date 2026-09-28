from pathlib import Path
import pytest

from runtime.failure_input_reduction import minimize_bytes, reduce_failure_fixture


def test_partition_reduction_preserves_trigger_with_bounded_attempts():
    reduced, count = minimize_bytes(b'xxBADyy', lambda data: b'BAD' in data, max_attempts=20)
    assert reduced == b'BAD' and count <= 20


def test_real_failure_fixture_reduction_keeps_source_and_repeated_signature(tmp_path):
    fixture = tmp_path / 'input.bin'
    original = b'prefix-prefix-BAD-suffix-suffix'
    fixture.write_bytes(original)
    (tmp_path / 'test_reader.py').write_text('''from pathlib import Path
def test_reader():
    if b'BAD' in Path('input.bin').read_bytes():
        raise AssertionError('invalid frame marker')
''')
    report = reduce_failure_fixture(tmp_path, fixture='input.bin', tests=['test_reader.py'], max_attempts=14)
    assert report['status'] == 'reduced'
    assert report['reduced_bytes'] < len(original)
    assert b'BAD' in Path(report['candidate']).read_bytes()
    assert report['baseline'][0]['signature'] == report['final_signature']
    assert fixture.read_bytes() == original and report['source_applied'] is False


def test_passing_test_is_not_a_failure_oracle(tmp_path):
    (tmp_path / 'input.bin').write_bytes(b'valid')
    (tmp_path / 'test_reader.py').write_text('def test_reader(): assert True\n')
    report = reduce_failure_fixture(tmp_path, fixture='input.bin', tests=['test_reader.py'], max_attempts=1)
    assert report['status'] == 'not_reproducible'


def test_excluded_private_file_is_rejected_before_reading(tmp_path, monkeypatch):
    private = tmp_path / 'config.json'
    private.write_text('{"secret": "do not read"}')
    original = Path.read_bytes
    def read(path):
        assert path != private, 'private fixture must not be read'
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    with pytest.raises(ValueError, match='not_in_source_inventory'):
        reduce_failure_fixture(tmp_path, fixture='config.json', tests=['test_reader.py'])
