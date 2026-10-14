"""Focus a failed Analyzer draft on its cited code, without accepting its decision."""
import json
from pathlib import Path

from .feature_workspace import digest, inventory, merge_reads, read_sources


def _objects(content):
    if not isinstance(content, str) or not 1 <= len(content.encode()) <= 64000:
        raise ValueError('feature_analysis_draft_size')
    decoder, objects, rest = json.JSONDecoder(), [], content.strip()
    while rest:
        value, end = decoder.raw_decode(rest)
        if not isinstance(value, dict) or len(objects) >= 12:
            raise ValueError('feature_analysis_draft_sequence')
        objects.append(value)
        rest = rest[end:].strip()
    return objects


def load_analysis_draft(prior, project, expected, goal):
    prior, project = Path(prior), Path(project).resolve()
    saved = json.loads((prior / 'source-inventory.json').read_text(encoding='utf-8'))
    report = json.loads((prior / 'report.json').read_text(encoding='utf-8'))
    if (saved != expected or inventory(project) != expected or report['goal'] != goal
            or Path(report['project']).resolve() != project):
        raise ValueError('feature_analysis_draft_identity')
    transcript = prior.parent / 'transcript.json'
    calls = json.loads(transcript.read_text(encoding='utf-8'))
    for call in reversed(calls):
        events = call.get('telemetry', [])
        if not events or any(e.get('provider_label') != 'feature:analyzer' for e in events):
            continue
        if call.get('status') != 'failed':
            continue
        payload = json.loads(call['messages'][1]['content'])
        evidence = call.get('response_evidence', [])
        if (not call.get('usage_known') or payload.get('goal') != goal or len(evidence) != 1):
            raise ValueError('feature_analysis_draft_not_bound')
        objects = _objects(evidence[0].get('content'))
        drafts = [o for o in objects if o.get('status') == 'ready']
        if (len(drafts) != 1 or any(o.get('status') not in ('read', 'ready') for o in objects)
                or not all(k in drafts[0] for k in ('analysis', 'scope', 'evidence', 'unknowns', 'user_outcome'))):
            raise ValueError('feature_analysis_draft_missing')
        citations = drafts[0]['evidence']
        if not citations or any(not any(
                s['path'] == c.get('path') and s['start'] <= c.get('start', 0)
                and s['end'] >= c.get('end', 10**9) for s in payload['sources']) for c in citations):
            raise ValueError('feature_analysis_draft_unobserved_citation')
        sources = merge_reads([], read_sources(project, expected, citations, max_bytes=32000))
        return {'draft': drafts[0], 'accepted': False, 'sources': sources,
                'transcript_sha256': digest(transcript.read_bytes()),
                'instruction': 'This previous Analyzer draft failed JSON validation and is NOT an accepted role decision. Recheck its cited source and return one fresh complete Analyzer object. Previously read files remain available through read requests; no code or tests were approved by this draft.'}
    raise ValueError('feature_analysis_draft_missing')
