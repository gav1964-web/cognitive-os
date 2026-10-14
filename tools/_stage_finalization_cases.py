"""Synthetic calibration tasks, never evidence of independent production quality."""
from pathlib import Path


def create_case(root: Path, index: int) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    cap = 80 + index
    functions = []
    for number in range(12):
        functions.extend([
            f'''def normalize_label_{number}(value: str) -> str:
    """Normalize whitespace and bound the size of a display label."""
    if not isinstance(value, str):
        raise TypeError("label must be text")
    value = value.strip()
    if not value:
        return ""
    pieces = value.split()
    if not pieces:
        return ""
    normalized = " ".join(pieces)
    if len(normalized) > {cap}:
        normalized = normalized[:{cap}]
    return normalized.lower()
''',
            f'''def bounded_sum_{number}(values: list) -> int:
    """Sum nonnegative counters with a bounded saturation value."""
    if not isinstance(values, list):
        raise TypeError("counters must be a list")
    total = 0
    for value in values:
        if not isinstance(value, int):
            raise TypeError("counter must be an integer")
        if value < 0:
            raise ValueError("counter must be nonnegative")
        total += value
        if total >= {cap}:
            return {cap}
    return total
''',
            f'''def normalize_record_{number}(record: dict) -> dict:
    """Normalize record keys and values and return sorted fields."""
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    normalized = {{}}
    for key, value in record.items():
        key = str(key).strip().lower()
        if not key:
            continue
        normalized[key] = str(value).strip()
    if not normalized:
        return {{}}
    ordered = sorted(normalized.items())
    return dict(ordered)
'''])
    source = '\n\n'.join(functions)
    supported_kinds = ['flat_module', 'package_relative_imports', 'future_annotations', 'explicit_exports',
        'crlf_source', 'unused_module_state', 'shared_label_constant', 'immutable_defaults',
        'shared_counter_constant', 'forward_builtin_annotation', 'comprehension_scope', 'unicode_source',
        'public_alias', 'importing_consumer', 'module_docstring', 'mixed_decorated_functions',
        'keyword_only_defaults', 'literal_tuple_defaults']
    kind = supported_kinds[index] if index < 18 else ''
    if kind == 'future_annotations':
        source = 'from __future__ import annotations\n\n' + source
    elif kind == 'explicit_exports':
        names = [f'{prefix}_{n}' for prefix in ('normalize_label', 'bounded_sum', 'normalize_record') for n in range(12)]
        source += '\n__all__ = ' + repr(names) + '\n'
    elif kind == 'unused_module_state':
        source = 'CACHE = {}\n' + source
    elif kind == 'shared_label_constant':
        source = 'EMPTY_LABEL = ""\n' + source.replace('return ""', 'return EMPTY_LABEL')
    elif kind == 'immutable_defaults':
        source = source.replace('(value: str)', '(value: str = "")')
    elif kind == 'shared_counter_constant':
        source = f'COUNTER_CAP = {cap}\n' + source.replace(f'total >= {cap}', 'total >= COUNTER_CAP')
    elif kind == 'forward_builtin_annotation':
        source = source.replace('value: str', 'value: "str"')
    elif kind == 'comprehension_scope':
        source = source.replace('pieces = value.split()', 'pieces = [part for part in value.split() if part]')
    elif kind == 'unicode_source':
        source = '# Нормализация имён и значений\n' + source.replace('display label', 'метки отображения')
    elif kind == 'public_alias':
        source += '\nnormalize = normalize_label_0\n'
    elif kind == 'module_docstring':
        source = '"""Project transforms retain stable public imports across internal refactors."""\n\n' + source
    elif kind == 'mixed_decorated_functions':
        source = 'def identity(function):\n    return function\n\n' + source.replace('def normalize_label_', '@identity\ndef normalize_label_')
    elif kind == 'keyword_only_defaults':
        source = source.replace('(value: str)', '(value: str, *, reserved: bool = False)')
    elif kind == 'literal_tuple_defaults':
        source = source.replace('(value: str)', '(value: str, options: tuple = (1, "stable"))')
    if index >= 18:
        kind = ['shared_state', 'decorators', 'dynamic_namespace', 'classes', 'global_dependencies',
                'oversized_function'][index - 18]
        if kind == 'shared_state':
            source = 'counter = 0\n' + source
            source = source.replace('    if not isinstance', '    global counter\n    counter += 1\n    if not isinstance')
        elif kind == 'decorators':
            source = 'def registered(function):\n    return function\n\n' + source.replace('def ', '@registered\ndef ')
        elif kind == 'dynamic_namespace':
            source = 'namespace = globals()\n' + source
        elif kind == 'classes':
            source = 'class Helpers:\n' + '\n'.join('    ' + line for line in source.splitlines())
        elif kind == 'global_dependencies':
            source = 'OPTIONS = {"enabled": True}\n' + source.replace('    if not isinstance',
                '    if not OPTIONS["enabled"]:\n        raise RuntimeError("disabled")\n    if not isinstance')
        else:
            source = 'def expand(value):\n' + '    value = value + 1\n' * 420 + '    return value\n'
    module_root, import_line, module_name = root, 'import transforms', 'transforms'
    if kind == 'package_relative_imports':
        module_root = root / 'sample_package'
        module_root.mkdir()
        (module_root / '__init__.py').write_text('')
        import_line, module_name = 'from sample_package import transforms', 'sample_package.transforms'
    (module_root / 'transforms.py').write_bytes(source.replace('\n', '\r\n' if kind == 'crlf_source' else '\n').encode('utf-8'))
    tests = root / 'tests'
    tests.mkdir()
    (tests / 'test_transforms.py').write_text(f'''import pickle
import pytest
{import_line}

@pytest.mark.parametrize("number", range(12))
def test_transforms(number):
    label = getattr(transforms, "normalize_label_" + str(number))
    total = getattr(transforms, "bounded_sum_" + str(number))
    record = getattr(transforms, "normalize_record_" + str(number))
    assert label(" A   B ") == "a b"
    assert label("X" * 200) == "x" * {cap}
    assert label("   ") == ""
    assert total([1, 2, 3]) == 6
    assert total([200]) == {cap}
    assert total([]) == 0
    assert record({{" B ": 2, " A": 1, " ": 3}}) == {{"a": "1", "b": "2"}}
    assert list(record({{"b": 2, "a": 1}})) == ["a", "b"]
    assert record({{}}) == {{}}
    for function in (label, total, record):
        assert function.__module__ == "{module_name}"
        assert pickle.loads(pickle.dumps(function)) is function
        with pytest.raises(TypeError):
            function(None)
    with pytest.raises(ValueError):
        total([-1])
''', encoding='utf-8')
    if kind in {'public_alias', 'explicit_exports', 'importing_consumer'}:
        with (tests / 'test_transforms.py').open('a', encoding='utf-8') as stream:
            if kind == 'public_alias':
                stream.write('\ndef test_alias():\n    assert transforms.normalize is transforms.normalize_label_0\n')
            elif kind == 'explicit_exports':
                stream.write('\ndef test_exports():\n    assert len(transforms.__all__) == 36\n    assert all(hasattr(transforms, n) for n in transforms.__all__)\n')
            else:
                (root / 'consumer.py').write_text('from transforms import normalize_label_0\ndef normalize(value):\n    return normalize_label_0(value)\n')
                stream.write('\ndef test_consumer():\n    from consumer import normalize\n    assert normalize(" X ") == "x"\n')
    return {'case_id': f'calibration-{index:02d}', 'kind': kind,
            'expected': 'completed' if index < 18 else 'needs_replanning',
            'source_lines': len(source.splitlines())}
