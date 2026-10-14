"""Freeze five synthetic claim jobs and separate expectations; never call a model."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.single_claim_review import prepare_claim_review, review_messages
from runtime.narrow_type_evidence_binding import content_digest

DEFAULT_CASES = Path(__file__).resolve().parents[1] / 'tests/fixtures/project_description/obligation_cases.json'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare_suite(cases_path, output, *, review_version=4):
    source = json.loads(Path(cases_path).read_text(encoding='utf-8'))
    cases = source.get('cases', [])
    if source.get('schema_version') != 'claim_obligation_cases.v1' or len(cases) != 5:
        raise ValueError('suite_requires_five_cases')
    ids = []
    for case in cases:
        if (set(case) != {'id', 'source', 'claim', 'expected_verdict', 'rationale'}
                or not isinstance(case['id'], str) or not re.fullmatch(r'case\d{2}', case['id'])
                or case['expected_verdict'] not in ('supported', 'refuted', 'uncertain')
                or not isinstance(case['source'], str) or not 1 <= len(case['source']) <= 10000
                or not isinstance(case['claim'], str) or not 1 <= len(case['claim']) <= 2000):
            raise ValueError('invalid_suite_case')
        ids.append(case['id'])
    if len(set(ids)) != 5:
        raise ValueError('duplicate_suite_case')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in cases:
        folder = output / case['id']
        folder.mkdir()
        path = folder / 'example.py'
        path.write_bytes(case['source'].encode('utf-8'))
        claim = {'text': case['claim'], 'evidence_ids': ['s1']}
        draft = {'purpose': claim, 'scenarios': [deepcopy(claim)], 'data_flow': [deepcopy(claim)],
                 'unknowns': [], 'confidence': 'medium'}
        report = {'status': 'described', 'raw_response': draft, 'description': deepcopy(draft),
            'evidence': {'root': folder.as_posix(), 'sources': [{'id': 's1', 'path': 'example.py',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'excerpt': case['source'],
                'authority': 'synthetic_source_fixture', 'truncated': False}]}}
        job = prepare_claim_review(report, 'scenarios.0', review_version=review_version)
        write(folder / 'report.json', report)
        write(folder / 'job.json', job)
        messages = review_messages(job)
        rows.append({'case': case['id'], 'job': f"{case['id']}/job.json", 'job_digest': job['digest'],
                     'messages_digest': content_digest(messages),
                     'request_characters': sum(len(m['content']) for m in messages),
                     'expected_verdict': case['expected_verdict'], 'rationale': case['rationale']})
    result = {'schema_version': 'claim_obligation_protocol.v1', 'status': 'prepared_not_run',
              'fixture_digest': content_digest(source), 'cases': rows, 'model_calls': 0,
              'review_version': review_version,
              'expectations_sent_to_model': False, 'independent_holdout': False,
              'live_budget_authorized': False, 'proposed_max_requests': 5,
              'max_requests_per_case': 1, 'timeout_seconds': 240, 'retries': 0, 'fallbacks': False,
              'max_completion_tokens_per_request': 3200,
              'judging': 'Separate semantic source review; structural validation alone is not a pass',
              'total_request_characters': sum(row['request_characters'] for row in rows)}
    write(output / 'protocol.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', default=str(DEFAULT_CASES))
    parser.add_argument('--output', required=True)
    parser.add_argument('--review-version', type=int, choices=[2, 3, 4], default=4)
    args = parser.parse_args()
    result = prepare_suite(args.cases, args.output, review_version=args.review_version)
    print(json.dumps({'status': result['status'], 'model_calls': 0,
                      'request_characters': result['total_request_characters']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
