"""Bounded claim evidence from supplied excerpts; lexical matches are not semantics."""
import json
import re
from .helper_context import select_context
from .context_allocation import allocations, requested
from .lookup_contract import lookup_kind


def quoted_terms(text):
    terms = []
    for match in re.finditer(r"`([^`\n]{2,96})`|'([^'\n]{2,96})'|\"([^\"\n]{2,96})\"|«([^»\n]{2,96})»", text):
        term = next(value for value in match.groups() if value is not None).strip()
        if term and term not in terms:
            terms.append(term)
    return terms[:8]


def occurrence(text, term):
    # A mention of `rapid` must not match `rapidly` or `rapid_mode`.
    return re.search(r'(?<![\w])' + re.escape(term) + r'(?![\w])', text)


def literal_matches(term, sources, *, limit=3):
    matches = []
    # Newly requested code is generally less abbreviated than initial excerpts.
    ordered = sorted(sources, key=lambda s: (s.get('authority') != 'requested_source_excerpt',
                                             s.get('truncated', False), s['id']))
    seen = set()
    for source in ordered:
        if source.get('authority') == 'documentation_claims':
            continue
        match = occurrence(source['excerpt'], term)
        key = (source['path'], source['sha256'])
        if not match or key in seen:
            continue
        seen.add(key)
        start, end = match.span()
        matches.append({'term': term, 'source_id': source['id'], 'path': source['path'],
                        'sha256': source['sha256'], 'excerpt_offset': start,
                        'context': source['excerpt'][max(0, start - 70):end + 90],
                        'authority': 'literal_presence_only'})
        if len(matches) >= limit:
            break
    return matches


def claim_packets(claims, evidence):
    return [{'claim_id': claim['id'], 'cited_source_ids': claim['evidence_ids'],
             'literal_matches': [match for term in quoted_terms(claim['text'])
                                 for match in literal_matches(term, evidence['sources'], limit=1)][:6],
             'semantic_status': 'unverified'} for claim in claims]


def _window(text, terms, budget):
    if budget <= 0:
        return ''
    if len(text) <= budget:
        return text
    marker = '\n[... excerpt omitted ...]\n'
    positions = [m.start() for term in terms if (m := occurrence(text, term))]
    if not positions:
        half = max(0, (budget - len(marker)) // 2)
        return (text[:half] + marker + (text[-half:] if half else ''))[:budget]
    positions = sorted(set(positions))[:6]
    share = max(0, (budget - len(marker) * len(positions)) // len(positions))
    chunks = []
    for position in positions:
        start = max(0, position - share // 3)
        chunks.append(text[start:start + share])
    return (marker.join(chunks) + marker)[:budget]


def review_context(evidence, claims, policy):
    """Bound the serialized evidence+packet object, without reading more files."""
    packets = claim_packets(claims, evidence)
    cited = {ref for claim in claims for ref in claim['evidence_ids']}
    wanted = {source['path'] for source in evidence['sources'] if source['id'] in cited}
    catalog = sorted((s for s in evidence.get('source_catalog', []) if lookup_kind(s['path'])),
                     key=lambda s: (s['path'] not in wanted, s['path']))
    catalog = [{'path': s['path'], 'symbols': s.get('symbols', [])[:12]}
               for s in catalog[:policy['max_catalog_entries']]]
    sources = [{key: source[key] for key in ('id', 'path', 'sha256', 'authority') if key in source}
               for source in evidence['sources']]
    for row, original in zip(sources, evidence['sources']):
        row.update(excerpt='', truncated=original.get('truncated', False))
        if requested(original):
            row.update(requested=True, supplied_excerpt_preserved=False, covered_by='')
    view = {'root': evidence['root'], 'sources': sources, 'source_catalog': catalog,
            'catalog_limited': evidence.get('catalog_limited', False) or len(catalog) < len(evidence.get('source_catalog', [])),
            'scope': 'Selected excerpts only. Missing text does not imply absent behavior. Literal matches do not prove claims.'}
    bundle = {'evidence': view, 'claim_packets': packets}
    size = lambda: len(json.dumps(bundle, ensure_ascii=False))
    limit = policy['max_context_characters']
    while size() > limit // 2 and catalog:
        catalog.pop()
        view['catalog_limited'] = True
    if size() > limit - 100 * len(sources):
        raise ValueError('description_claim_context_metadata_budget')
    # JSON escaping can expand source text; shrink in a second bounded pass.
    originals = evidence['sources']
    shares, protected, aliases = allocations(originals, policy, max(0, limit - size()), cited)
    for index, covering in aliases.items():
        sources[index]['covered_by'] = sources[covering]['id']
    terms = list(dict.fromkeys(term for claim in claims for term in quoted_terms(claim['text'])))
    def excerpt(original, share):
        selected = select_context(original['excerpt'], share) if original['path'].endswith('.py') else None
        return selected if selected is not None else _window(original['excerpt'], terms, share)
    for row, original, share in zip(sources, originals, shares):
        row['excerpt'] = excerpt(original, share)
        row['truncated'] = row['truncated'] or len(row['excerpt']) < len(original['excerpt'])
        if requested(original):
            row['supplied_excerpt_preserved'] = row['excerpt'] == original['excerpt']
    while size() > limit:
        choices = [i for i, s in enumerate(sources) if i not in protected and s['excerpt']]
        if not choices:
            raise ValueError('description_requested_context_budget')
        index = max(choices, key=lambda i: len(sources[i]['excerpt']))
        row = sources[index]
        original = next(s for s in originals if s['id'] == row['id'])
        row['excerpt'] = excerpt(original, max(0, len(row['excerpt']) // 2))
        row['truncated'] = True
        if requested(original):
            row['supplied_excerpt_preserved'] = False
    bundle['context_characters'] = size()
    return bundle
