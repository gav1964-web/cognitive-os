"""Let COS develop a user goal in a Python project; opt-in verified source apply."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.feature_acceptance import save
from runtime.feature_development import run_feature_development
from runtime.feature_workspace import inventory
from runtime.feature_inference import FeatureChat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--goal', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--python')
    parser.add_argument('--apply-source', action='store_true')
    parser.add_argument('--carry-unknown-ledger')
    parser.add_argument('--replay-from', help='Reuse exact successful requests from a same-source prior run')
    parser.add_argument('--resume-context', help='Reuse source ranges previously selected by COS, after hash checks')
    parser.add_argument('--resume-roles', help='Resume at SpecWriter from a same-source run with completed analysis/design')
    parser.add_argument('--stop-after', choices=['spec_writer'])
    parser.add_argument('--fresh-spec', action='store_true', help='Reuse roles/source and native observations, but regenerate rejected tests from scratch')
    parser.add_argument('--extend-spec', action='store_true', help='Add Python acceptance while retaining qualified checkpoint tests unchanged')
    parser.add_argument('--resume-candidate', action='store_true', help='Reverify the saved passing candidate and resume review without regenerating code')
    parser.add_argument('--observations', help='Source/candidate-bound verification artifact observations for review')
    parser.add_argument('--resume-review-draft', action='store_true', help='Continue an unaccepted same-candidate review draft with full patch/tests and cited sources')
    parser.add_argument('--resume-analysis-draft', action='store_true', help='Recheck a failed same-source Analyzer draft using its previously observed citations; fresh decision required')
    parser.add_argument('--spec-format', choices=['python', 'json_calls'], default='python')
    parser.add_argument('--max-spec-attempts', type=int, choices=[1, 2, 3], default=2)
    parser.add_argument('--budget-limit', type=int, default=1000000)
    parser.add_argument('--budget-authorization', help='Explicit user grant required above the default series ceiling; carry remains mandatory')
    parser.add_argument('--max-calls', type=int, default=12)
    parser.add_argument('--max-input-bytes', type=int, default=80000)
    parser.add_argument('--max-output-tokens', type=int, default=32768)
    args = parser.parse_args()
    if not 1 <= args.max_calls <= 12 or not 1000 <= args.max_input_bytes <= 160000:
        parser.error('max-calls1..12 and max-input-bytes1000..160000 required')
    if not 1 <= args.budget_limit <= 10000000 or (args.stop_after and args.apply_source):
        parser.error('invalid budget-limit; stop-after cannot apply source')
    if args.budget_limit > 1000000 and (not args.budget_authorization or not args.carry_unknown_ledger):
        parser.error('extended budget requires explicit authorization and carried ledger')
    if not 1 <= args.max_output_tokens <= 32768:
        parser.error('max-output-tokens1..32768 required')
    if args.resume_roles and (args.replay_from or args.resume_context):
        parser.error('resume-roles replaces replay-from and resume-context')
    if args.extend_spec and (not args.resume_roles or args.fresh_spec or args.spec_format != 'python'):
        parser.error('extend-spec requires resume-roles, python format and no fresh-spec')
    if args.resume_candidate and (not args.resume_roles or args.fresh_spec or args.extend_spec or args.stop_after):
        parser.error('resume-candidate requires resume-roles and no spec generation/stop flags')
    if args.resume_review_draft and not args.resume_candidate:
        parser.error('resume-review-draft requires resume-candidate')
    if args.resume_analysis_draft and (not args.resume_context or args.resume_roles):
        parser.error('resume-analysis-draft requires resume-context without resume-roles')
    project, output = Path(args.project_dir).resolve(), Path(args.output).resolve()
    if output.exists() or output.is_relative_to(project) or project.is_relative_to(output):
        parser.error('output must be a fresh directory outside the target project')
    python = Path(args.python).resolve() if args.python else next(
        (p for p in [project / '.venv/Scripts/python.exe', project / '.venv/bin/python'] if p.is_file()),
        Path(sys.executable))
    output.mkdir(parents=True)
    save(output / 'request.json', {'goal': args.goal, 'project': str(project),
         'apply_source_authorized': args.apply_source, 'python': str(python),
         'max_calls': args.max_calls, 'source_author': 'COS role workflow',
         'reservation_scope': f'sequential admission below{args.budget_limit}; upstream internal billing not independently attested',
         'carry_unknown_ledger': args.carry_unknown_ledger,
         'resume_roles': args.resume_roles, 'stop_after': args.stop_after, 'fresh_spec': args.fresh_spec,
         'spec_format': args.spec_format, 'extend_spec': args.extend_spec,
         'max_output_tokens': args.max_output_tokens,
         'resume_candidate': args.resume_candidate,
         'observations': args.observations,
         'resume_review_draft': args.resume_review_draft,
         'resume_analysis_draft': args.resume_analysis_draft,
         'budget_authorization': args.budget_authorization,
         'budget_limit_exclusive': args.budget_limit})
    previous = []
    if args.replay_from:
        prior = Path(args.replay_from)
        request = json.loads((prior / 'request.json').read_text(encoding='utf-8'))
        expected = json.loads((prior / 'run/source-inventory.json').read_text(encoding='utf-8'))
        if request['goal'] != args.goal or request['project'] != str(project) or inventory(project) != expected:
            raise ValueError('feature_replay_requires_same_goal_project_and_source')
        previous = json.loads((prior / ('transcript.json' if (prior / 'transcript.json').exists()
                                      else 'calls.json')).read_text(encoding='utf-8'))
    chat = FeatureChat(output, max_calls=args.max_calls, max_input_bytes=args.max_input_bytes,
                       carry=args.carry_unknown_ledger, previous=previous, budget_limit=args.budget_limit,
                       budget_authorization=args.budget_authorization)
    result = run_feature_development(project=project, work=output / 'run', goal=args.goal,
               python=python, chat=chat, apply_source=args.apply_source,
               resume_context=args.resume_context, resume_roles=args.resume_roles,
               stop_after=args.stop_after, max_spec_attempts=args.max_spec_attempts,
               fresh_spec=args.fresh_spec, spec_format=args.spec_format, extend_spec=args.extend_spec,
               max_output_tokens=args.max_output_tokens, resume_candidate=args.resume_candidate,
               observations=args.observations, resume_review_draft=args.resume_review_draft,
               resume_analysis_draft=args.resume_analysis_draft)
    result['inference'] = {'calls': len(chat.attempts),
        'replayed_calls': len(chat.replayed),
        'reported_tokens': sum(e.get('total_tokens', 0) or 0 for row in chat.attempts for e in row['telemetry']),
        'new_unknown_calls': sum(not row.get('usage_known', False) for row in chat.attempts)}
    save(output / 'result.json', result)
    print(json.dumps({k: result.get(k) for k in ('status', 'reason', 'source_apply',
                     'delivered_scope', 'limitations', 'inference')}, ensure_ascii=False))
    return 0 if result['status'] in ('verified', 'installed', 'spec_qualified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
