"""Bounded automatic retry after verified full native regression feedback."""
import json
from pathlib import Path

from .development_regression_feedback import build_regression_feedback, feedback_messages, candidate_identity
from .narrow_type_evidence_binding import content_digest
from .project_development_core import run_project_development
from .stage_finalization_workspace import inventory


def run_regression_cycle(*, root, project_dir, goal, task_contract, chain_case, policy,
                         config, chat, work_dir, max_attempts=2, authorized=False, training_replay=True):
    if not authorized or not callable(chat):
        raise ValueError('authorized_budgeted_model_cycle_required')
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError('one_to_three_development_attempts_required')
    if type(training_replay) is not bool:
        raise ValueError('explicit_training_replay_mode_required')
    root, project, work = Path(root).resolve(), Path(project_dir).resolve(), Path(work_dir).resolve()
    if (not work.is_relative_to(root/'artifacts') or work.exists()
            or work.is_relative_to(project) or project.is_relative_to(work)):
        raise ValueError('fresh_campaign_workspace_required')
    work.mkdir(parents=True)
    before = inventory(project)
    report = {'schema_version':'development_regression_cycle.v1','status':'running',
        'max_attempts':max_attempts,'attempts':[],'source_inventory_digest':content_digest(before),
        'task_contract':task_contract,'source_apply':False,'automatic_retry':False,
        'training_replay':training_replay,'independence_established':False}
    feedback, rejected = None, set()
    def persist():
        (work/'cycle.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def model_chat(messages, *, config):
        if inventory(project) != before:
            raise ValueError('source_changed_before_cycle_inference')
        outgoing = feedback_messages(messages,feedback,project) if feedback else messages
        from .local_inference import LocalInferenceError
        from .inference_failure_evidence import failure_evidence
        try:
            value = chat(outgoing,config=config)
        except LocalInferenceError as exc:
            if evidence := failure_evidence(exc):
                report['provider_failure'] = evidence
                pending = {'goal': goal, 'project_dir': str(project), 'messages': outgoing,
                    'task_contract': task_contract, 'source_inventory_digest': content_digest(before),
                    'requested_model': getattr(config, 'model', None), 'resume_requires_source_check': True}
                (work/'pending-inference.json').write_text(
                    json.dumps(pending, ensure_ascii=False, indent=2), encoding='utf-8')
            raise
        if rejected and isinstance(value,dict) and isinstance(value.get('candidates'),list):
            for candidate in value['candidates']:
                if isinstance(candidate,dict) and isinstance(candidate.get('replacement_source'),str):
                    if candidate_identity(candidate['replacement_source'],candidate.get('additional_replacements')) in rejected:
                        raise ValueError('previously_rejected_candidate_repeated')
        return value
    persist()
    try:
        for index in range(max_attempts):
            report['automatic_retry'] = index > 0
            record={'attempt':index+1,'status':'started','feedback_digest':feedback['digest'] if feedback else None}
            report['attempts'].append(record)
            persist()
            result=run_project_development(root=root,project_dir=project,goal=goal,
                task_contract=task_contract,chain_case=chain_case,policy=policy,llm_hypothesis_config=config,
                model_chat=model_chat,run_role_chain=True,run_sandbox_experiment=True,
                validate_causal_proposals=True,authorize_training_replay=training_replay,
                authorize_model_trial=not training_replay)
            if report.get('provider_failure'):
                result.update(provider_failure=report['provider_failure'], quality_evaluation='not_evaluated')
            path=work/f'attempt-{index+1}.json'
            path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            record.update(status=result['status'],result_path=str(path),result_digest=content_digest(result))
            persist()
            if inventory(project) != before:
                raise ValueError('source_changed_during_development_cycle')
            if report.get('provider_failure'):
                report.update(status='controlled_stop', reason='provider_unavailable',
                    quality_evaluation='not_evaluated', resume_path=str(work/'pending-inference.json'))
                break
            if result['status']=='experiment_validated':
                report['status']='experiment_validated'
                break
            report['status']='controlled_stop'
            if index+1 == max_attempts:
                report['reason']='development_attempt_budget_exhausted'
                break
            try:
                feedback=build_regression_feedback(project,result,work/f'feedback-{index+1}',authorized=True)
                if feedback['status']!='verified':
                    raise ValueError('native_regression_feedback_not_reproduced')
            except (ValueError,OSError,KeyError,TypeError) as exc:
                report['reason']=str(exc)
                break
            rejected.add(feedback['candidate_function_identity'])
            record['verified_feedback_digest']=feedback['digest']
            persist()
    except Exception as exc:
        report.update(status='controlled_stop',reason=str(exc),error_type=type(exc).__name__)
        if report.get('provider_failure'):
            report.update(reason='provider_unavailable', quality_evaluation='not_evaluated',
                          resume_path=str(work/'pending-inference.json'))
        raise
    finally:
        report['source_unchanged']=inventory(project)==before
        persist()
    return report
