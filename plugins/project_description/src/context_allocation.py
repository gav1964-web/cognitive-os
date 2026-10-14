"""Reserve complete explicitly requested excerpts before supporting context."""
import json

from .excerpts import _allocations
from .helper_context import sections


def requested(source):
    return source.get('requested') is True or source.get('authority') == 'requested_source_excerpt'


def weight(source, cited):
    if requested(source):
        return 16
    path = source['path'].replace('\\', '/').lower()
    if (any(part in ('tests', 'test', 'docs') for part in path.split('/'))
            or source.get('authority') == 'documentation_claims'):
        return 1
    return 8 if source['id'] in cited else 2


def allocations(sources, policy, budget, cited):
    limits = [policy.get('max_requested_source_characters', policy['max_source_characters'])
              if requested(s) else policy['max_source_characters'] for s in sources]
    protected, shares, aliases = set(), [0] * len(sources), {}
    for i, source in enumerate(sources):
        text = source['excerpt']
        encoded = len(json.dumps(text, ensure_ascii=False)) - 2
        covering = next((j for j in sorted(protected) if j not in aliases
                         and covers(sources[j], source)), None)
        if covering is not None and len(sources[covering]['id']) <= budget:
            aliases[i] = covering
            protected.add(i)
            budget -= len(sources[covering]['id'])
            continue
        if requested(source) and len(text) <= limits[i] and encoded <= budget:
            shares[i] = len(text)
            budget -= encoded
            protected.add(i)
    pending = [i for i in range(len(sources)) if i not in protected]
    extra = _allocations([min(len(sources[i]['excerpt']), limits[i]) for i in pending],
                         budget, [weight(sources[i], cited) for i in pending])
    for i, amount in zip(pending, extra):
        shares[i] = amount
    return shares, protected, aliases


def covers(kept, candidate):
    """Only exact complete sections from the same hashed lookup may share bytes."""
    if (not requested(candidate) or not requested(kept)
            or any(s.get('truncated') or not s.get('helper_context') for s in (kept, candidate))
            or (kept['path'], kept['sha256']) != (candidate['path'], candidate['sha256'])
            or not all(s['excerpt'].startswith('[lines ') for s in (kept, candidate))):
        return False
    available, wanted = sections(kept['excerpt']), sections(candidate['excerpt'])
    return bool(wanted) and all(row['complete'] and any(
        row['name'] == other['name'] and row['text'] == other['text'] and other['complete']
        for other in available) for row in wanted)
