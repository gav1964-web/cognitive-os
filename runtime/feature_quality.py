"""Bounded autonomous ownership routing around the existing verified feature workflow."""
from pathlib import Path

from .feature_acceptance import save
from .feature_checkpoint import verified_candidate, rejected_candidate, qualified_spec, pending_spec
from .feature_spec_witness import RejectedCandidateWitness
from .feature_quality_challenge import challenge_with_feedback, check_campaign
from .feature_development import run_feature_development
from .feature_quality_chat import QualityChat
from .feature_workspace import inventory, read_sources
from .feature_quality_routing import reconsider_review_owner
from .feature_progress import conflicting_failures
from plugins.development_quality.src.source_evidence import review_has_counterexample


def route_failure(result):
    reason = result.get('reason', '')
    if reason in ('feature_resumed_candidate_changed_or_failed', 'feature_rejected_candidate_changed'):
        return None  # Passing native tests cannot waive a failed candidate identity check.
    if reason in ('feature_call_count_exhausted', 'feature_next_call_budget_exhausted', 'feature_stop_requested'):
        return None  # Never reroute a settled stop to another role.
    if reason.startswith('feature_test_reference_'):
        return None  # Broken runtime input references cannot be repaired by Writer.
    if reason == 'feature_frozen_test_echo_changed':
        return 'programmer'
    if reason.startswith('feature_review_rejected:'):
        owner = result['artifacts'].get('reviewer', {}).get('repair_owner')
        return owner if owner in ('architect', 'spec_writer', 'programmer') else 'programmer'
    if reason.startswith(('feature_baseline_', 'feature_test_', 'feature_new_tests',
                          'feature_existing_regression', 'feature_tests_', 'quality_role_correction_limit:spec_writer')):
        return 'spec_writer'
    if reason.startswith('quality_role_correction_limit:architect'):
        return 'architect'
    if reason.startswith(('feature_acceptance_failed', 'feature_edit_', 'feature_replacement')):
        return 'programmer'
    if (result.get('attempts') and result['attempts'][-1].get('passed')
            and not any(x in reason for x in ('budget', 'unknown', 'source_changed', 'stale', 'mismatch'))):
        return 'reviewer'
    return None


def run_quality_development(*, project, work, goal, python, chat, configs,
                            max_cycles=4, challenges=True, human_interventions=None,
                            resume_roles=None, resume_rejected_review=False,
                            require_rejected_candidate_witness=False,
                            require_baseline_expectations=False, resume_candidate_from=None,
                            audit_mode='always'):
    project, work = Path(project).resolve(), Path(work).resolve()
    if (work.exists() or not 1 <= max_cycles <= 6 or work.is_relative_to(project) or project.is_relative_to(work)
            or resume_candidate_from and not resume_roles):
        raise ValueError('quality_fresh_work_and_bounded_cycles_required')
    work.mkdir(parents=True)
    expected = inventory(project)
    q = QualityChat(chat, work, expected=expected,
                    require_baseline_expectations=require_baseline_expectations, audit_mode=audit_mode)
    human_interventions = list(human_interventions or [])
    q.record('run_started', human_interventions=human_interventions, source_hashes=expected)
    report = {'schema_version': 'feature_quality.v1', 'goal': goal, 'status': 'running',
              'require_baseline_expectations': require_baseline_expectations, 'audit_mode': audit_mode,
              'baseline_expectation_scope': 'newly authored specifications; historical frozen checkpoints retain their original contract',
              'source_hashes': expected, 'cycles': [], 'source_apply': False,
              'human_interventions': human_interventions, 'challenges_requested': challenges}
    prior, owner, mutation_feedback = None, None, None
    campaign, campaign_hashes, retained_candidate = None, None, None
    pending_revision, revision_count = None, 0
    progress = []
    try:
        if resume_roles:
            resume_roles = str(Path(resume_roles).resolve())
            if resume_rejected_review:
                from .feature_quality_resume import restore_rejected_review
                prior, retained_candidate = restore_rejected_review(q, resume_roles, project, expected, goal)
                owner = reconsider_review_owner(q, prior, configs['spec_writer'], route_failure(prior), force=True)
                if owner in ('programmer', 'spec_writer') and review_has_counterexample(prior['artifacts']['reviewer']):
                    owner = 'spec_writer'
                    q.record('review_counterexample_requires_test', review=prior['artifacts']['reviewer'])
                q.feedback = {'owner': owner, 'review': prior['artifacts']['reviewer'],
                              'instruction': 'Repair the rejected candidate or acceptance; preserve accepted tests.'}
                report['resumed_rejected_review'] = str(resume_roles)
            elif qualified_spec(resume_roles) is not None:
                from .feature_quality_resume import restore_qualified_spec, restore_pending_candidate, restore_failed_candidate
                if restore_failed_candidate(q, resume_roles, project, expected, goal):
                    owner = 'programmer'
                elif restore_pending_candidate(q, resume_roles, project, expected, goal):
                    owner = 'reviewer'
                    resume_roles = str(Path(resume_roles).resolve())
                    if challenges:
                        from .feature_quality_challenge import restore_campaign
                        campaign, campaign_hashes = restore_campaign(resume_roles)
                        if campaign:
                            q.record('challenge_campaign_restored', checkpoint=resume_roles,
                                     variants=len(campaign['challenges']), grants_approval=False)
                else:
                    resume_roles = restore_qualified_spec(q, resume_roles, project, expected, goal)
                report['resumed_qualified_spec'] = resume_roles
            elif pending_spec(resume_roles) is not None:
                from .feature_quality_resume import restore_native_rejected_spec
                resume_roles = restore_native_rejected_spec(q, resume_roles, project, expected, goal)
                report['resumed_native_rejected_spec'] = resume_roles
                if 'spec_writer' in q.unaccepted or 'spec_writer' in q.pending:
                    owner = 'spec_writer'
            else:
                from .feature_quality_resume import restore_spec_draft
                resume_roles = restore_spec_draft(q, resume_roles, project, expected, goal)
                report['resumed_unqualified_spec'] = resume_roles
            if challenges and campaign is None:
                from .feature_quality_challenge import restore_campaign
                campaign, campaign_hashes = restore_campaign(resume_roles)
                if campaign:
                    q.record('challenge_campaign_restored', checkpoint=resume_roles,
                             variants=len(campaign['challenges']), grants_approval=False)
            if challenges and resume_candidate_from:
                from .feature_quality_challenge import restore_campaign
                restored, hashes = restore_campaign(resume_candidate_from)
                if campaign and restored and (campaign != restored or campaign_hashes != hashes):
                    raise ValueError('quality_prior_candidate_campaign_conflict')
                if restored:
                    campaign, campaign_hashes = restored, hashes
                    q.record('challenge_campaign_restored', checkpoint=str(resume_candidate_from),
                             variants=len(campaign['challenges']), grants_approval=False)
        for cycle in range(max_cycles):
            q.cycle = cycle
            if inventory(project) != expected:
                raise ValueError('quality_original_source_changed')
            run_dir = work / f'cycle-{cycle}'
            q.retained = {}
            q.spec_witness = None
            if prior and owner == 'architect':
                q.retained['analyzer'] = prior['artifacts']['analyzer']
            if owner == 'spec_writer' and retained_candidate:
                q.retained['programmer'] = retained_candidate['proposal']
                review = retained_candidate.get('review', {})
                if review and (require_rejected_candidate_witness or review_has_counterexample(review)):
                    q.spec_witness = RejectedCandidateWitness(project=project, expected=expected,
                        candidate=retained_candidate, frozen=q.frozen,
                        allowed=prior['artifacts']['architect']['scope'],
                        work=work / f'spec-witness-{cycle}', python=python)
            resume = report['cycles'][-1]['checkpoint'] if report['cycles'] and prior and owner != 'architect' else None
            if cycle == 0 and resume_roles and owner != 'architect':
                resume = resume_roles
            if resume and owner == 'spec_writer' and rejected_candidate(resume):
                # run_feature_development itself replays this proposal first.
                # Leaving a second copy queued would suppress the next real repair.
                q.retained.pop('programmer', None)
            revision_context = None
            if pending_revision:
                revision_context = resume
                resume = None
                q.retained.update({r: prior['artifacts'][r] for r in ('analyzer', 'architect')})
                q.retained['programmer'] = pending_revision['proposal']
                from .feature_quality_draft import draft_binding
                from .narrow_type_evidence_binding import content_digest
                q.unaccepted['spec_writer'] = {'binding': draft_binding({'goal': goal,
                    'artifacts': prior['artifacts'], 'source_inventory_digest': content_digest(expected)},
                    'spec_writer'), 'proposal': pending_revision['specification']}
                pending_revision = None
            result = run_feature_development(project=project, work=run_dir, goal=goal,
                python=python, chat=q, configs=configs, resume_roles=resume,
                resume_context=revision_context,
                progress=progress,
                resume_candidate=owner == 'reviewer', fresh_spec=owner == 'spec_writer',
                resume_candidate_from=resume_candidate_from if cycle == 0 else None,
                max_spec_attempts=2, apply_source=False)
            report['cycles'].append({'checkpoint': str(run_dir), 'status': result['status'],
                                     'reason': result.get('reason')})
            save(work / 'report.json', report)
            spec = result['artifacts'].get('spec_writer')
            if spec:
                q.freeze_specification(spec, goal=goal, design=result['artifacts']['architect'])
            if result.get('attempts') and result['attempts'][-1].get('passed'):
                retained_candidate = rejected_candidate(run_dir) or verified_candidate(run_dir)
            if owner == 'architect':
                retained_candidate = None
            if (result['status'] == 'verified' and challenges and q.needs_audit('challenger',
                    scope=result['artifacts']['architect']['scope'], retained_campaign=bool(campaign),
                    feedback=any(not a.get('passed') for a in result.get('attempts', [])))):
                candidate = verified_candidate(run_dir)
                candidate_root = run_dir / f'attempt-{len(result["attempts"])}' / 'project'
                candidate_inventory = inventory(candidate_root)
                allowed = result['artifacts']['architect']['scope']
                sources = []
                for name in allowed:
                    sources.extend(read_sources(candidate_root, candidate_inventory, [{'path': name}], max_bytes=50000))
                payload = {'goal': goal, 'design': result['artifacts']['architect'],
                           'candidate_sources': sources, 'allowed': allowed,
                           'frozen_acceptance': spec,
                           'instruction': 'Fault witnesses are independent of acceptance. Do not merely introduce syntax/import errors.'}
                production_hashes = {k: v for k, v in candidate_inventory.items() if not k.startswith('tests/')}
                if campaign and campaign_hashes == production_hashes:
                    proposal = campaign
                    q.record('artifact_reused', role='challenger', reason='same candidate; recheck fixed fault campaign with expanded tests')
                    checked = check_campaign(candidate=candidate_root, work=work / f'challenges-{cycle}',
                        python=python, specification=spec, allowed=allowed, challenges=proposal['challenges'])
                    if checked['status'] in ('passed', 'needs_specification'):
                        save(work / f'challenges-{cycle}-retained.json', {
                            'candidate_hashes': candidate_inventory, 'challenges': proposal['challenges'],
                            'validation': str(work / f'challenges-{cycle}/report.json'), 'grants_approval': False})
                else:
                    proposal, checked = challenge_with_feedback(q, configs['spec_writer'], payload,
                        candidate=candidate_root, work=work / f'challenges-{cycle}',
                        python=python, spec=spec, allowed=allowed)
                if checked['status'] in ('passed', 'needs_specification'):
                    campaign, campaign_hashes = proposal, production_hashes
                report['cycles'][-1]['challenges'] = checked
                if checked['status'] == 'passed':
                    report.update(status='verified', checkpoint=str(run_dir), goal_complete=result.get('goal_complete'),
                                  challenge_status='passed', candidate_hashes=candidate['candidate_hashes'])
                    break
                if checked['status'] == 'needs_specification':
                    owner = 'spec_writer'
                    mutation_feedback = {'survivors': [
                        {'reason': v['reason'], 'witness': proposal['challenges'][i]['oracle_tests']}
                        for i, v in enumerate(checked['variants']) if v['status'] == 'survived'],
                        'instruction': 'Add these missing behavior checks without altering frozen tests or weakening the user goal.'}
                else:
                    report.update(status='blocked', reason='quality_challenge_inconclusive')
                    break
            elif result['status'] == 'verified':
                report.update(status='verified', checkpoint=str(run_dir), goal_complete=result.get('goal_complete'),
                              challenge_status='not_triggered' if challenges else 'not_requested')
                break
            else:
                if result.get('reason') == 'feature_candidate_no_progress' or conflicting_failures(result):
                    if revision_count:
                        report.update(status='blocked', reason='quality_spec_revision_limit')
                        break
                    from .feature_spec_dispute import resolve_dispute
                    revision_count += 1
                    pending_revision = resolve_dispute(q, result, configs['spec_writer'],
                        project=project, expected=expected, checkpoint=run_dir, python=python, goal=goal)
                    if not pending_revision:
                        report.update(status='blocked', reason='quality_spec_dispute_unresolved')
                        break
                    report.setdefault('spec_revisions', []).append(pending_revision['receipt'])
                    q.frozen = pending_revision['specification']['tests']
                    q.accepted_metadata = None  # Revised metadata needs ordinary native qualification.
                    q.pending.pop('spec_writer', None)
                    retained_candidate = None
                    campaign, campaign_hashes = None, None
                    owner = 'spec_writer'
                    q.feedback = {'owner': owner, 'spec_revision': pending_revision['receipt'],
                        'instruction': 'Independently audit and requalify this narrowly revised preservation assertion; goal and all other tests unchanged.'}
                    q.record('feedback_routed', owner=owner, phase='spec_revision', feedback=q.feedback)
                    prior = result
                    continue
                owner = route_failure(result)
                owner = reconsider_review_owner(q, result, configs['spec_writer'], owner)
                review = result.get('artifacts', {}).get('reviewer', {})
                if (owner in ('programmer', 'spec_writer') and retained_candidate
                        and review_has_counterexample(review)):
                    owner = 'spec_writer'
                    q.record('review_counterexample_requires_test', review=review)
                if owner != 'spec_writer':
                    mutation_feedback = None
                if owner is None:
                    report.update(status='blocked', reason=result.get('reason'))
                    break
            q.feedback = mutation_feedback or {'owner': owner, 'reason': result.get('reason'),
                         'review': result['artifacts'].get('reviewer'),
                         'instruction': 'Fix the owned defect; keep already verified facts and immutable tests.'}
            q.record('feedback_routed', owner=owner, phase='cycle', feedback=q.feedback)
            prior = result
        else:
            report.update(status='blocked', reason='quality_cycle_limit')
    except Exception as exc:
        report.update(status='blocked', reason=str(exc))
    report['source_unchanged'] = inventory(project) == expected
    if not report['source_unchanged']:
        report.update(status='blocked', reason='quality_original_source_changed')
    report['autonomy'] = {'automatic_routes': sum(e['event'] == 'feedback_routed' for e in q.events),
                          'human_interventions': len(human_interventions),
                          'model_calls': sum(e['event'] == 'call_returned' for e in q.events),
                          'scope': 'within invocation only; task/fixture creation is external'}
    save(work / 'report.json', report)
    return report
