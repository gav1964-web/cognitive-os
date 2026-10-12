"""Check cited excerpts; a matching quote never establishes a causal claim."""
import re
from copy import deepcopy


def _citation_hint(lines, quote, start, end):
    """Locate exact bytes only within supplied contiguous source ranges."""
    matches = _quote_locations(lines, quote)
    if len(matches) == 1:
        first, last = matches[0]
        return (f'; exact quote occurs at supplied lines {first}-{last}. '
                'Resubmit the corrected citation; this hint grants no acceptance.')
    excerpt = '\n'.join(f'{n}: {lines[n][:160]}' for n in range(start, min(end, start + 5) + 1)
                        if n in lines)
    location = 'multiple locations' if matches else 'no location'
    return (f'; exact quote has {location} in supplied source. '
            f'Numbered excerpt (omit display numbers from quote):\n{excerpt}')


def _quote_locations(lines, quote):
    groups = []
    for number in sorted(lines):
        if not groups or number != groups[-1][-1] + 1:
            groups.append([])
        groups[-1].append(number)
    matches = []
    needle = quote.strip() if isinstance(quote, str) else ''
    if needle:
        for group in groups:
            body = '\n'.join(lines[n] for n in group)
            offset = body.find(needle)
            while offset >= 0 and len(matches) < 2:
                first = group[0] + body[:offset].count('\n')
                matches.append((first, first + needle.count('\n')))
                offset = body.find(needle, offset + 1)
            if len(matches) == 2:
                break
    return matches


def repair_citations(artifact, sources):
    """Repair only a uniquely located exact quote, never its text or finding."""
    result, changes = deepcopy(artifact), []
    rows = result.get('evidence')
    if not isinstance(rows, list):
        return {'artifact': result, 'changes': changes, 'grants_approval': False}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        start, end = row.get('start'), row.get('end')
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            continue
        lines, conflict = {}, False
        for source in sources:
            if source.get('path') != row.get('path'):
                continue
            for number, line in enumerate(source.get('content', '').splitlines(), source.get('start', 1)):
                if number in lines and lines[number] != line:
                    conflict = True
                lines[number] = line
        quote = row.get('quote')
        if conflict or not isinstance(quote, str) or not quote.strip():
            continue
        if all(n in lines for n in range(start, end + 1)) and quote.strip() in '\n'.join(lines[n] for n in range(start, end + 1)):
            continue
        matches = _quote_locations(lines, quote)
        if len(matches) != 1:
            continue
        row['start'], row['end'] = matches[0]
        changes.append({'evidence_index': index, 'path': row.get('path'),
                        'before': [start, end], 'after': list(matches[0]),
                        'basis': 'unique_exact_quote_in_supplied_source'})
    return {'artifact': result, 'changes': changes, 'grants_approval': False}


def validate_evidence(artifact, sources):
    rows = artifact.get('evidence', [])
    if not isinstance(rows, list):
        return ['analysis evidence must be a list']
    issues = []
    for row in rows:
        if not isinstance(row, dict):
            issues.append('analysis evidence must contain source references')
            continue
        path, start, end = (row.get(k) for k in ('path', 'start', 'end'))
        if (not isinstance(path, str) or type(start) is not int or type(end) is not int
                or not 1 <= start <= end):
            issues.append('analysis evidence requires a path and positive inclusive line range')
            continue
        lines = {}
        for src in sources:
            if src.get('path') == path:
                first = src.get('start', 1)
                lines.update(enumerate(src.get('content', '').splitlines(), first))
        if any(i not in lines for i in range(start, end + 1)):
            issues.append(f'evidence range is not fully supplied: {path}:{start}-{end}')
            continue
        excerpt = '\n'.join(lines[i] for i in range(start, end + 1))
        quote = row.get('quote')
        if not isinstance(quote, str) or not quote.strip() or quote.strip() not in excerpt:
            issues.append(f'evidence needs an exact nonempty quote inside its range: {path}:{start}-{end}'
                          + _citation_hint(lines, quote, start, end))
        symbol = row.get('symbol')
        if symbol is not None and (not isinstance(symbol, str) or not symbol
                or not re.search(r'\b' + re.escape(symbol.rsplit('.', 1)[-1]) + r'\b', excerpt)):
            issues.append(f'evidence symbol is absent from cited excerpt: {path}:{start}-{end}')
    return issues


def review_has_counterexample(review):
    rows = review.get('counterexamples')
    return (review.get('decision') == 'reject' and isinstance(rows, list) and bool(rows)
            and all(isinstance(row, dict) and all(k in row and row[k] is not None
                and (not isinstance(row[k], str) or bool(row[k].strip()))
                for k in ('input', 'expected', 'observed', 'goal_clause')) for row in rows))
