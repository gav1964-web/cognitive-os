"""Resolve declared plugin test ownership without guessing names or reading prose."""
import json
import re
from pathlib import Path, PureWindowsPath


class TestOwnershipError(ValueError):
    """An installed plugin cannot be assigned an existing bounded test suite."""


def resolve_plugin_test_paths(root: Path, plugin_ids) -> dict[str, list[Path]]:
    root = root.resolve()
    ids = sorted(plugin_ids)
    if not ids:
        raise TestOwnershipError('no_installed_plugins')
    owners = {}
    for ident in ids:
        if not re.fullmatch(r'[A-Za-z_]\w*', ident):
            raise TestOwnershipError('invalid_plugin_id')
        manifest = (root/'plugins'/ident/'plugin.json').resolve()
        if not manifest.is_relative_to(root):
            raise TestOwnershipError(f'{ident}:manifest_escapes_project')
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise TestOwnershipError(f'{ident}:unreadable_manifest') from exc
        if not isinstance(data, dict):
            raise TestOwnershipError(f'{ident}:invalid_manifest')
        declared = data['test_paths'] if 'test_paths' in data else [f'plugins/{ident}/tests']
        if not isinstance(declared, list) or not 1 <= len(declared) <= 64:
            raise TestOwnershipError(f'{ident}:nonempty_bounded_test_paths_required')
        resolved = []
        for name in declared:
            if (not isinstance(name, str) or not name.strip() or len(name) > 1000
                    or any(c in name for c in '*?[]:\x00\n\r')
                    or Path(name).is_absolute() or PureWindowsPath(name).drive
                    or PureWindowsPath(name).is_absolute()
                    or '..' in name.replace('\\', '/').split('/')):
                raise TestOwnershipError(f'{ident}:literal_project_relative_path_required')
            path = (root/name).resolve()
            if not path.is_relative_to(root):
                raise TestOwnershipError(f'{ident}:test_path_escapes_project')
            if path.is_dir():
                tests = [p for p in path.rglob('*.py') if _test_name(p)]
                if not tests:
                    raise TestOwnershipError(f'{ident}:empty_test_directory')
                if any(not p.resolve().is_relative_to(root) for p in tests):
                    raise TestOwnershipError(f'{ident}:nested_test_path_escapes_project')
            elif not path.is_file() or path.suffix != '.py':
                raise TestOwnershipError(f'{ident}:missing_python_test_path')
            if path not in resolved:
                resolved.append(path)
        owners[ident] = resolved
    return owners


def _test_name(path):
    return path.name.startswith('test_') or path.name.endswith('_test.py')
