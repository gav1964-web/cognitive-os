"""One eligibility rule for advertised and performed bounded text lookups."""
from pathlib import Path


def lookup_kind(name):
    path = Path(name)
    if any(p.startswith('.') or p == '..' for p in path.parts) or path.is_absolute():
        return None
    if path.name.lower().startswith('readme') and path.suffix.lower() in {'', '.md', '.rst', '.txt'}:
        return 'documentation_claims'
    if path.suffix.lower() in {'.py', '.js', '.ts', '.tsx', '.html'}:
        return 'requested_source_excerpt'
    return None
