"""Advisory work items preserve draft identity without promoting draft assertions."""
import hashlib
import json


def review_tasks(report, claims):
    originals = {row['id']: row for row in claims}
    reviews = {row['claim_id']: row for row in report.get('claim_reviews', [])}
    sources = {row['id']: row for row in report['evidence']['sources']}
    tasks = []
    for finding in report.get('review_audit', {}).get('findings', []):
        claim = originals[finding['claim_id']]
        refs = set(claim['evidence_ids']) | {m['source_id'] for m in finding.get('matches', [])}
        bound = [{key: sources[ref][key] for key in ('id', 'path', 'sha256')} for ref in sorted(refs)]
        identity = {'root': report['evidence']['root'], 'claim': claim, 'finding': finding, 'sources': bound}
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
        tasks.append({'id': 'description-review-' + digest, 'status': 'open',
                      'claim_namespace': 'draft', 'claim_id': claim['id'], 'draft_text': claim['text'],
                      'review_reason': reviews.get(claim['id'], {}).get('reason'),
                      'finding': finding, 'sources': bound,
                      'next_action': 'Review claim meaning and conditions against source; resolve explicitly. Do not auto-restore.',
                      'authority': 'advisory_review_task', 'execution_authorized': False})
    return tasks
