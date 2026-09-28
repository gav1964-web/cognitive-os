"""Apply plugin contracts and bounded role-local feedback with a durable journal."""
import json
import time
from dataclasses import replace

from plugins.development_quality.src.main import run as quality_contract
from .feature_acceptance import save
from .feature_quality_draft import (draft_binding, missing_draft_files,
                                   correction_feedback, frozen_test_mismatches)
from .feature_test_references import compact_test_references


class QualityChat:
    def __init__(self, transport, work):
        self.transport, self.work = transport, work
        self.policy = quality_contract({'action': 'policy'})['policy']
        self.events, self.retained, self.frozen = [], {}, []
        self.feedback = None
        self.pending = {}
        self.unaccepted = {}
        self.spec_witness = None
        self.cycle = 0

    def record(self, event, **fields):
        self.events.append({'event': event, 'cycle': self.cycle, **fields})
        save(self.work / 'autonomy.json', {'schema_version': 'feature_autonomy.v1',
             'scope': 'events inside this invocation; external task/fixture authorship is not independence',
             'events': self.events})

    def call(self, messages, config):
        messages = [dict(m) for m in messages]
        messages[0]['content'] = 'Return one JSON object only.\n' + messages[0]['content']
        role = config.provider_label.partition(':')[2]
        if len(messages) == 2:
            payload, count = compact_test_references(json.loads(messages[1]['content']))
            if count:
                messages[1]['content'] = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
                messages[0]['content'] += ('\nInput tests with content_reference contain the exact code '
                    'of the test with the same path in the named field (immutable_previous_tests '
                    'or specification.tests). Read that complete code. Return full literal test '
                    'contents, never references, in your output.')
                self.record('test_content_referenced', role=role, occurrences=count)
        started = time.monotonic()
        try:
            value = self.transport(messages, config=config)
        except Exception as exc:
            self.record('call_failed', role=role, reason=str(exc), seconds=time.monotonic()-started)
            raise
        self.record('call_returned', role=role, status=value.get('status', value.get('decision')),
                    seconds=round(time.monotonic()-started, 3))
        return value

    def __call__(self, messages, *, config):
        role = config.provider_label.partition(':')[2]
        if role in self.retained:
            self.record('artifact_reused', role=role)
            return self.retained.pop(role)
        payload = json.loads(messages[1]['content'])
        binding = draft_binding(payload, role)
        pending = self.pending.get(role)
        if pending and pending['binding'] == binding:
            payload['quality_contract_feedback'] = pending['feedback']
        elif pending:
            self.pending.pop(role)
        if self.feedback:
            payload['quality_feedback'] = self.feedback
        instruction = messages[0]['content'] + '\n' + self.policy.get(role, '')
        if role == 'spec_writer' and self.frozen:
            payload['immutable_previous_tests'] = self.frozen
            instruction += ('\nRetain these prior accepted tests byte-for-byte; return them unchanged '
                            'plus separate new files for uncovered cases. Do not replace old tests. '
                            'Include case_plan covering the complete merged suite.')
        for ordinal in range(self.policy['max_format_repairs'] + 1):
            restored = self.unaccepted.pop(role, None)
            if restored and restored['binding'] != binding:
                raise ValueError('quality_unaccepted_proposal_binding_changed')
            value = restored['proposal'] if restored else self.call([{'role': 'system', 'content': instruction},
                               {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}], config)
            if value.get('status') != 'ready' or role not in ('analyzer', 'architect', 'spec_writer'):
                return value
            issues = quality_contract({'action': 'validate', 'role': role, 'artifact': value,
                                       'sources': payload.get('sources', [])})['issues']
            previous = payload.get('quality_contract_feedback')
            case_continuity = None
            if role == 'spec_writer' and previous and not issues:
                case_continuity = quality_contract({'action': 'compare_draft',
                    'previous': previous['rejected'], 'current': value})
                if case_continuity['unexplained']:
                    issues.append({'draft_case_continuity': case_continuity})
            if role == 'spec_writer' and self.frozen:
                submitted = {t['path']: t['content'] for t in value.get('tests', [])}
                mismatches = frozen_test_mismatches(self.frozen, submitted)
                if mismatches:
                    issues.append({'immutable_test_mismatches': mismatches})
            if role == 'architect' and not issues:
                audit = self.call([{'role': 'system', 'content': self.policy['design_auditor']},
                    {'role': 'user', 'content': json.dumps({'goal': payload['goal'], 'sources': payload['sources'],
                         'analysis': payload.get('artifacts', {}).get('analyzer'), 'design': value}, ensure_ascii=False, separators=(',', ':'))}],
                    replace(config, provider_label='quality:design_auditor'))
                save(self.work / f'design-audit-{self.cycle}-{ordinal}.json', audit)
                if audit.get('decision') != 'approve':
                    issues.append({'design_audit': audit})
            if role == 'spec_writer' and not issues and self.spec_witness:
                issues.extend(self.spec_witness(value))
            if role == 'spec_writer' and not issues:
                audit = self.call([{'role': 'system', 'content': self.policy['spec_auditor']},
                    {'role': 'user', 'content': json.dumps({'goal': payload['goal'],
                        'execution_stage': 'specification_audit_before_native_qualification',
                        'sources': payload['sources'], 'design': payload.get('artifacts', {}).get('architect'),
                        'previous_unaccepted_draft': previous,
                        'omitted_previous_draft_files': missing_draft_files(previous['rejected'], value) if previous else [],
                        'draft_case_continuity': case_continuity,
                        'specification': value}, ensure_ascii=False, separators=(',', ':'))}],
                    replace(config, provider_label='quality:spec_auditor'))
                save(self.work / f'spec-audit-{self.cycle}-{ordinal}.json', audit)
                if audit.get('decision') != 'approve':
                    issues.append({'acceptance_audit': audit})
            if not issues:
                self.pending.pop(role, None)
                return value
            self.record('feedback_routed', owner=role, phase='artifact_admission', issues=issues)
            payload['quality_contract_feedback'] = correction_feedback(value, issues, previous)
            # A read request re-enters __call__; keep the draft and its audit
            # until admission, including across bounded owner-routing cycles.
            self.pending[role] = {'binding': binding, 'feedback': payload['quality_contract_feedback']}
        raise ValueError('quality_role_correction_limit:' + role)
