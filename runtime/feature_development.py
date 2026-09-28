"""User-goal to model-owned tests/code, native comparison and COS installation.

Separate opt-in workflow: does not weaken native-failure replay authorities or
the legacy programmer executor's non-applying contract.
"""
import json
from dataclasses import replace
from pathlib import Path

from .feature_acceptance import prepare, verify, save, specification_feedback, execution_feedback, review_baseline_context
from .feature_workspace import (inventory, catalog, read_sources, materialize_edits,
                                install, digest, owned_path, merge_reads, proposal_for_context)
from .feature_prompts import COMMON, ROLE, JSON_CASES
from .feature_case_compiler import compile_cases
from .feature_context import select_context
from .feature_context_reads import read_request
from .feature_extension import load_extension, merge_extension, verify_extension
from .role_inference import role_model_config
from .feature_checkpoint import load_roles, pending_spec, previous_native_feedback, qualified_spec, observed_regressions, latest_read_paths
from .feature_checkpoint import verified_candidate, rejected_candidate, review_reads, candidate_matches
from .narrow_type_evidence_binding import content_digest
from .local_inference import LocalInferenceError
from .feature_review_patch import candidate_patch


def run_feature_development(*, project, work, goal, python, chat, apply_source=False,
                            configs=None, max_attempts=2, resume_context=None,
                            resume_roles=None, stop_after=None, max_spec_attempts=2,
                            fresh_spec=False, spec_format='python', extend_spec=False,
                            max_output_tokens=32768, resume_candidate=False, observations=None,
                            resume_review_draft=False, resume_analysis_draft=False):
    project, work = Path(project).resolve(), Path(work).resolve()
    if (not goal.strip() or work.exists() or work.is_relative_to(project)
            or project.is_relative_to(work) or max_attempts not in (1, 2)
            or max_spec_attempts not in (1, 2, 3) or stop_after not in (None, 'spec_writer')
            or (stop_after and apply_source) or spec_format not in ('python', 'json_calls')
            or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768
            or (resume_candidate and (not resume_roles or fresh_spec or extend_spec or stop_after))
            or (resume_review_draft and not resume_candidate)
            or (resume_analysis_draft and (not resume_context or resume_roles))
            or (extend_spec and (not resume_roles or fresh_spec or spec_format != 'python'))):
        raise ValueError('feature_requires_goal_and_fresh_external_workdir')
    work.mkdir(parents=True)
    report = {'schema_version': 'feature_development.v1', 'goal': goal,
              'project': str(project), 'status': 'running', 'source_apply': False,
              'authors': {'goal': 'user', 'analysis_design_tests_code': 'COS model roles',
                          'application': 'COS verified transaction'},
              'artifacts': {}, 'attempts': [], 'spec_format': spec_format}
    try:
        expected = inventory(project)
        save(work / 'source-inventory.json', expected)
        ctx = {'goal': goal, 'catalog': catalog(project, expected), 'sources': [],
               'source_inventory_digest': content_digest(expected),
               'copy_scope': 'text sources <=2MB only; excludes binary corpus, runtime data, legacy/archive/backups'}
        resume_context = resume_context or resume_roles
        pending_reads = []
        analysis_draft = None
        if resume_context:
            prior = Path(resume_context)
            old = json.loads((prior / 'source-context.json').read_text(encoding='utf-8'))
            old_inventory = json.loads((prior / 'source-inventory.json').read_text(encoding='utf-8'))
            if old_inventory != expected or old['goal'] != goal:
                raise ValueError('feature_resume_context_stale_or_different_goal')
            # Re-read only the ranges selected by the previous COS model. Never
            # trust editable cached source excerpts as current source evidence.
            rows = []
            for row in old['sources']:
                rows.extend(read_sources(project, expected, [row], max_bytes=65000))
            ctx['sources'] = merge_reads([], rows)
            from .feature_checkpoint import recover_pending_read
            recovered = recover_pending_read(prior, project, expected)
            if recovered:
                ctx['sources'] = merge_reads(ctx['sources'], recovered)
                report['recovered_duplicate_read'] = [
                    {k: r[k] for k in ('path', 'start', 'end')} for r in recovered]
            ctx['catalog'] = [{k: r[k] for k in ('path', 'lines')} for r in ctx['catalog']]
            report['resumed_model_selected_context'] = str(prior)
            save(work / 'source-context.json', ctx)
        if resume_analysis_draft:
            from .feature_analysis_draft import load_analysis_draft
            analysis_draft = load_analysis_draft(resume_context, project, expected, goal)
            save(work / 'retained-source-context.json', ctx)
            ctx['sources'] = analysis_draft.pop('sources')
            report['unaccepted_analysis_draft'] = analysis_draft
            save(work / 'source-context.json', ctx)
        if resume_roles:
            artifacts, pending_reads = load_roles(resume_roles, project, expected, goal,
                                                  transcript_context=not extend_spec)
            report['artifacts'].update(artifacts)
            report['resumed_roles'] = str(Path(resume_roles).resolve())
            for role, value in artifacts.items():
                save(work / (role + '.json'), value)
        extension = load_extension(resume_roles) if extend_spec else None
        if extension:
            report['inherited_specification'] = {'checkpoint': str(resume_roles),
                                                'test_hashes': extension['test_hashes']}
        observed = observed_regressions(resume_roles, expected) if resume_roles else {'files': []}
        report['observed_regression_scope'] = observed
        if spec_format == 'json_calls' and fresh_spec:
            pending_reads = []
        save(work / 'source-context.json', ctx)
        save(work / 'spec-source-ranges.json', [
            {k: row[k] for k in ('path', 'start', 'end')} for row in pending_reads])
        role_configs = configs or {r: replace(role_model_config(r), fallbacks=(),
                                  max_output_tokens=max_output_tokens,
                                  timeout_seconds=max(240, role_model_config(r).timeout_seconds))
                                  for r in ('analyzer', 'architect', 'spec_writer')}

        def ask(role, extra=None):
            feedback = None
            read_errors = []
            fresh_reads = recover_pending_read(resume_roles, project, expected, role, errors=read_errors) if resume_roles else []
            repeated_reads = 0
            format_corrections = 0
            role_reads = list(pending_reads) if role == 'spec_writer' else []
            if role in ('programmer', 'reviewer'):
                role_reads = review_reads(resume_roles, project, expected, role, errors=read_errors) if resume_roles else []
                role_reads = merge_reads(role_reads, review_reads(work, project, expected, role, errors=read_errors))
                save(work / (role + '-source-ranges.json'), [
                    {k: row[k] for k in ('path', 'start', 'end')} for row in role_reads])
                if role == 'reviewer' and resume_review_draft:
                    role_reads = []  # The bound draft carries prior observations; source remains readable.
            if read_errors:
                feedback = {'errors': read_errors, 'instruction': 'Restored read requests retain the same catalog authority. Missing draft/new files are artifacts, not source files; use the supplied proposal and exact catalog paths.'}
            recent_paths = latest_read_paths(resume_roles) if extension else set()
            for _ in range(6):
                payload = {**ctx, 'artifacts': report['artifacts'], **(extra or {})}
                if role == 'analyzer' and analysis_draft:
                    payload['unaccepted_analysis_draft'] = analysis_draft
                if feedback:
                    payload['read_tool_result'] = feedback
                payload = select_context(payload, role=role, ctx=ctx, artifacts=report['artifacts'],
                    extra=extra, role_reads=role_reads, fresh_reads=fresh_reads, recent_paths=recent_paths,
                    extension=extension, spec_format=spec_format, project=project, expected=expected, observed=observed)
                cfg = role_configs[role if role in role_configs else 'spec_writer']
                if role in ('spec_writer', 'reviewer'):
                    # Hash checks remain in read_sources and saved checkpoints;
                    # these roles do not write source-hash-bound edits.
                    payload['sources'] = [{k: v for k, v in row.items() if k != 'sha256'}
                                          for row in payload['sources']]
                instruction = JSON_CASES if role == 'spec_writer' and spec_format == 'json_calls' else ROLE[role]
                try:
                    response = chat([{'role': 'system', 'content': COMMON + instruction},
                                     {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}],
                                    config=replace(cfg, provider_label='feature:' + role))
                except LocalInferenceError as exc:
                    if format_corrections or str(exc) != 'structured response is not a complete JSON object':
                        raise
                    format_corrections += 1
                    feedback = {'invalid_format': str(exc), 'instruction':
                        'Return exactly ONE complete JSON object. No duplicate object, analysis, channel markers, code fences or commentary. No decision was accepted.'}
                    continue
                if not isinstance(response, dict):
                    raise ValueError('feature_role_response_not_object')
                if role == 'reviewer' and response.get('status') == response.get('decision') == 'reject':
                    # An explicit negative decision cannot authorize a patch.
                    # Retain the model spelling while routing its substantive rejection.
                    response = {**response, 'status': 'ready', 'original_model_status': 'reject'}
                required = {'analyzer': ('analysis', 'scope', 'evidence', 'unknowns', 'user_outcome'),
                            'architect': ('design', 'scope', 'preserve', 'risks', 'acceptance'),
                            'spec_writer': ('cases' if spec_format == 'json_calls' else 'tests', 'regression_tests', 'acceptance', 'limitations'),
                            'programmer': ('edits',),
                            'reviewer': ('decision', 'reason', 'delivered_scope', 'limitations', 'goal_complete')}
                missing = ([k for k in ('reads',) if not response.get(k)] if response.get('status') == 'read'
                           else [k for k in required[role] if k not in response]
                           if response.get('status') == 'ready' else [])
                if role == 'programmer' and response.get('status') == 'ready':
                    paths = [e.get('path') for e in response.get('edits', []) if isinstance(e, dict)]
                    if len(paths) != len(set(paths)):
                        missing.append('unique edit paths: combine all replacements for a file in one entry')
                    allowed = report['artifacts']['architect']['scope']
                    frozen_paths = {t['path'] for t in report['artifacts']['spec_writer']['tests']}
                    outside = [p for p in paths if p not in allowed and p not in frozen_paths]
                    if outside:
                        missing.append('unauthorized edit paths: ' + ','.join(map(str, outside))
                            + '; return only the design production scope; tests belong to SpecWriter')
                if missing:
                    if format_corrections:
                        raise ValueError('feature_role_format_repeated:' + ','.join(missing))
                    format_corrections += 1
                    feedback = {'invalid_response': response, 'missing_required_fields': missing,
                                'instruction': 'Return the complete role object or a nonempty reads array. Prior source contents are already provided.'}
                    continue
                if response.get('status') == 'read':
                    rows, read_errors = read_request(project, expected, response['reads'])
                    fresh_reads = merge_reads(fresh_reads, rows)
                    recent_paths = {r['path'] for r in rows}
                    role_reads = merge_reads(role_reads, rows)
                    if role in ('programmer', 'reviewer'):
                        save(work / (role + '-source-ranges.json'), [
                            {k: row[k] for k in ('path', 'start', 'end')} for row in role_reads])
                    if role == 'spec_writer':
                        pending_reads[:] = role_reads
                        save(work / 'spec-source-ranges.json', [
                            {k: row[k] for k in ('path', 'start', 'end')} for row in role_reads])
                    # Read tools are not granted write/command execution authority.
                    before = ctx['sources']
                    ctx['sources'] = merge_reads(before, rows)
                    feedback = {'returned_ranges': [{k: v for k, v in r.items() if k != 'content'} for r in rows],
                                'errors': read_errors,
                                'already_present': bool(rows) and not read_errors and all(any(p['path'] == r['path'] and p['start'] <= r['start']
                                    and p['end'] >= r['end'] for p in payload['sources']) for r in rows),
                                'instruction': 'Read the supplied sources; produce your decision or identify a specific unprovided range.'}
                    repeated_reads = repeated_reads + 1 if feedback['already_present'] else 0
                    if repeated_reads >= 2:
                        raise ValueError('feature_repeated_read_without_progress:' + role)
                    ctx['catalog'] = [{k: r[k] for k in ('path', 'lines')} for r in ctx['catalog']]
                    save(work / 'source-context.json', ctx)
                    continue
                if response.get('status') != 'ready':
                    raise ValueError('feature_role_blocked:' + str(response.get('reason', role)))
                return response
            raise ValueError('feature_role_read_round_limit:' + role)

        for role in ('analyzer', 'architect'):
            value = report['artifacts'].get(role) or ask(role)
            if role in ('analyzer', 'architect'):
                raw_scope = value.get('scope')
                if isinstance(raw_scope, list) and role == 'architect':
                    test_context = [n for n in raw_scope if isinstance(n, str) and n.startswith('tests/')]
                    if test_context:
                        value = {**value, 'model_proposed_scope': raw_scope,
                                 'scope': [n for n in raw_scope if n not in test_context],
                                 'non_writable_test_context': test_context,
                                 'contract_note': 'Existing tests are read-only context. SpecWriter must create separate new tests; no edits to old tests are authorized.'}
                scope = value.get('scope')
                if not isinstance(scope, list) or not 1 <= len(scope) <= 4:
                    raise ValueError('feature_production_scope_required')
                for name in scope:
                    owned_path(project, name)
                    if not name.endswith('.py') or name.startswith('tests/'):
                        raise ValueError('feature_initial_python_scope_only')
            report['artifacts'][role] = value
            save(work / (role + '.json'), value)
        feedback = None
        frozen = qualified_spec(resume_roles) if resume_roles and not fresh_spec and not extension else None
        if frozen and frozen['format'] != spec_format:
            raise ValueError('feature_frozen_spec_format_changed')
        recovered_spec = pending_spec(resume_roles) if resume_roles and not fresh_spec and not extension else None
        if frozen:
            recovered_spec = frozen['raw']
        prior_native = previous_native_feedback(resume_roles) if resume_roles else None
        if fresh_spec:
            feedback = {'previous_native_attempt': prior_native,
                        'instruction': 'Revise the specification against the design, source and feedback. Preserve explicitly frozen accepted tests byte-for-byte. Correct unaccepted drafts while retaining valid coverage; drafts grant no approval. Native failures below are observations. Fresh audit and native qualification remain mandatory.'}
            report['fresh_spec_requested'] = True
        report['spec_attempts'] = []
        for ordinal in range(1, max_spec_attempts + 1):
            if ordinal == 1 and recovered_spec is not None:
                spec = recovered_spec
                report['rechecked_spec_from'] = str(Path(resume_roles).resolve())
            else:
                spec = ask('spec_writer', {'feedback': feedback})
            save(work / f'spec-proposal-{ordinal}.json', spec)
            acceptance = work / ('acceptance' if ordinal == 1 else f'acceptance-{ordinal}')
            raw_spec = spec
            try:
                if extension:
                    save(work / f'spec-extension-proposal-{ordinal}.json', spec)
                    spec = merge_extension(extension, spec)
                    save(work / f'spec-proposal-{ordinal}.json', spec)
                    raw_spec = spec
                if spec_format == 'json_calls':
                    spec = compile_cases(project, expected, spec, report['artifacts']['architect']['scope'])
                if frozen and spec != frozen['accepted']:
                    raise ValueError('feature_frozen_spec_changed')
                tests, baseline = prepare(project, acceptance, expected, spec, python)
                if extension:
                    verify_extension(extension, baseline)
            except (ValueError, SyntaxError, KeyError, TypeError) as exc:
                if frozen:
                    raise
                evidence = acceptance / 'baseline.json'
                feedback = {'rejected_spec': raw_spec, 'reason': str(exc),
                            'baseline': specification_feedback(json.loads(evidence.read_text(encoding='utf-8'))) if evidence.exists() else None,
                            'previous_native_attempt': prior_native,
                            'instruction': 'Keep meaningful assertion failures RED against current production; these are the desired feature gaps, not test bugs. Correct only fixture/import/API/contract errors. Never implement, mock or replace production behavior in tests. New APIs cannot be called directly before implementation. Choose runnable existing regression nodeids within copy_scope; disclose unavailable corpus coverage. Never modify or skip old tests.'}
                report['spec_attempts'].append({'status': 'rejected', 'feedback': feedback})
                if feedback['baseline']:
                    prior_native = {'specification_digest': content_digest(raw_spec),
                                    'baseline': feedback['baseline']}
                save(work / 'report.json', report)
                if ordinal == max_spec_attempts:
                    raise
                continue
            report['spec_attempts'].append({'status': 'qualified', 'acceptance': str(acceptance)})
            break
        report['artifacts']['spec_writer'] = spec
        if spec.get('test_authoring', {}).get('python_scaffolding'):
            report['authors']['analysis_design_tests_code'] = 'COS model roles; test semantics are model authored'
            report['authors']['test_scaffolding'] = 'runtime.feature_case_compiler'
        save(work / 'spec_writer.json', spec)
        report['baseline'] = baseline
        report['frozen_test_hashes'] = {n: digest(b) for n, b in tests.items()}
        if inventory(project) != expected:
            raise ValueError('feature_original_source_changed')
        if stop_after == 'spec_writer':
            report.update(status='spec_qualified', goal_complete=False,
                          limitations=spec['limitations'])
            save(work / 'report.json', report)
            return report
        feedback = None
        candidate = verified_candidate(resume_roles) if resume_candidate else None
        rejected = rejected_candidate(resume_roles) if not resume_candidate else None
        if candidate:
            report['resumed_candidate'] = str(Path(resume_roles).resolve())
        for ordinal in range(1, max_attempts + 1):
            proposal = (candidate['proposal'] if candidate else rejected['proposal'] if rejected and ordinal == 1
                        else ask('programmer', {'feedback': feedback}))
            save(work / f'proposal-{ordinal}.json', proposal)
            edits = materialize_edits(project, expected, proposal['edits'],
                                      report['artifacts']['architect']['scope'], frozen_tests=tests)
            report['exact_frozen_test_echoes'] = [e['path'] for e in proposal['edits'] if e['path'] in tests]
            checked = verify(project, work / f'attempt-{ordinal}', expected,
                             tests, edits, spec, baseline, python)
            report['attempts'].append(checked)
            save(work / 'report.json', report)
            if rejected and ordinal == 1 and not candidate_matches(rejected['candidate_hashes'], checked['candidate_hashes'], tests, allow_test_extension=fresh_spec):
                raise ValueError('feature_rejected_candidate_changed')
            if candidate and (not checked['passed'] or checked['candidate_hashes'] != candidate['candidate_hashes']):
                raise ValueError('feature_resumed_candidate_changed_or_failed')
            if checked['passed'] and not (rejected and ordinal == 1 and rejected.get('review')):
                break
            feedback = {'rejected_proposal': proposal_for_context(proposal, tests), 'verification': execution_feedback(checked),
                        'review': rejected.get('review') if rejected and ordinal == 1 else None}
        else:
            raise ValueError('feature_acceptance_failed')
        review_baseline = review_baseline_context(baseline, checked)
        additional_evidence = None
        if observations:
            from .feature_evidence import load_observations
            additional_evidence = load_observations(observations, expected, checked['candidate_hashes'])
            report['additional_observations'] = additional_evidence
        draft = None
        if resume_review_draft:
            from .feature_checkpoint import review_draft
            draft = review_draft(resume_roles, proposal_for_context(proposal, tests), spec)
            report['resumed_unaccepted_review_draft'] = True
        review = ask('reviewer', {'proposal': proposal_for_context(proposal, tests), 'verification': checked,
                                  'candidate_patch': candidate_patch(project, expected, edits),
                                  'baseline': review_baseline,
                                  'additional_evidence': additional_evidence,
                                  'unaccepted_previous_draft': draft,
                                  'previous_review_error': candidate['previous_error'] if candidate else None,
                                  'format_requirement': 'Exactly one complete JSON object. No repeated object, commentary or channel markers.'})
        report['artifacts']['reviewer'] = review
        save(work / 'reviewer.json', review)
        if review.get('decision') != 'approve':
            raise ValueError('feature_review_rejected:' + str(review.get('reason')))
        if inventory(project) != expected:
            raise ValueError('feature_original_source_changed')
        report.update(status='verified', goal_complete=review.get('goal_complete') is True,
                      delivered_scope=review.get('delivered_scope'),
                      limitations=review.get('limitations'))
        if apply_source:
            report['installation'] = install(project, expected, {**tests, **edits}, work / 'backup')
            report.update(status='installed', source_apply=True)
    except Exception as exc:
        report.update(status='blocked', reason=str(exc), error_type=type(exc).__name__)
    save(work / 'report.json', report)
    return report
