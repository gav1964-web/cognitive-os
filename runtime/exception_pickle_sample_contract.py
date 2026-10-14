"""Registered sample-descriptor client; project file IO stays in runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .competency_knowledge import ROOT, invoke_knowledge


def sample_constructor_values(
    names: list[str], *, source: str | None = None, class_name: str = '',
    object_contracts: dict[str, Any] | None = None, competency_root: Path = ROOT,
) -> list[Any]:
    """Return ordered descriptors, with None for unsupported inputs; no execution."""
    payload = {'operation': 'sample_values', 'names': names,
               'object_contracts': object_contracts or {}}
    if source is not None:
        payload.update(source=source, class_name=class_name)
    result = invoke_knowledge('exception_pickle', payload, root=competency_root)
    samples = result.get('samples')
    if result.get('status') != 'ok' or not isinstance(samples, list) or len(samples) != len(names):
        raise ValueError('invalid_exception_pickle_sample_response')
    return samples


def sample_constructor_value(
    name: str, *, object_contracts: dict[str, Any] | None = None,
) -> Any:
    return sample_constructor_values([name], object_contracts=object_contracts)[0]


def sample_constructor_value_for_source_file(
    name: str, *, source_file: Path, class_name: str,
    object_contracts: dict[str, Any] | None = None,
) -> Any:
    return sample_constructor_values(
        [name], source=_read_source(source_file), class_name=class_name,
        object_contracts=object_contracts,
    )[0]


def constructor_sample_call(
    *, source_file: Path, class_name: str, required: list[str], samples: list[Any],
) -> tuple[list[Any], dict[str, Any]]:
    try:
        source = _read_source(source_file)
    except OSError:
        return samples, {}
    result = invoke_knowledge('exception_pickle', {
        'operation': 'constructor_call', 'source': source, 'class_name': class_name,
        'required': required, 'samples': samples,
    })
    if (result.get('status') != 'ok' or not isinstance(result.get('args'), list)
            or not isinstance(result.get('kwargs'), dict)):
        raise ValueError('invalid_exception_pickle_constructor_call_response')
    return result['args'], result['kwargs']


def _read_source(path: Path) -> str:
    if not path.is_file():
        return ''
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-8', errors='replace')
