"""Recover catalog typos without relaxing source/private-path authority."""
from .feature_workspace import owned_path, permitted, read_sources


def read_request(project, expected, requests):
    if not isinstance(requests, list) or not 1 <= len(requests) <= 12:
        raise ValueError('feature_read_count')
    valid, errors = [], []
    for item in requests:
        name = item['path']
        if name in expected:
            valid.append(item)
            continue
        path = owned_path(project, name)
        if not permitted(name) or path.exists():
            raise ValueError('feature_read_not_in_inventory')
        errors.append({'path': name, 'error': 'not_in_source_inventory',
                       'instruction': 'Use an exact catalog path. Draft/new files are not on disk.'})
    rows = read_sources(project, expected, valid, max_bytes=52000) if valid else []
    return rows, errors
