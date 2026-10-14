"""Plugin-owned, explicitly bounded classification of test data syntax."""
import json
from pathlib import Path, PurePosixPath


def test_data_syntax_path(value: str) -> bool:
    normalized = value.replace('\\', '/')
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or '..' in path.parts or ':' in normalized:
        return False
    policy = json.loads((Path(__file__).parents[1] / 'knowledge/source_health.json').read_text(encoding='utf-8'))
    if policy.get('schema_version') != 'project_map_source_health.v1':
        return False
    return any(normalized.startswith(prefix) for prefix in policy['test_data_prefixes'])
