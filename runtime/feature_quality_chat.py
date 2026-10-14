"""Apply plugin contracts and bounded role-local feedback with a durable journal."""
import json
import time
from dataclasses import replace

from plugins.development_quality.src.main import run as quality_contract
from .feature_acceptance import save
from .feature_quality_draft import (draft_binding, missing_draft_files,
                                   correction_feedback, frozen_test_mismatches)
from .feature_test_references import compact_test_references
from .feature_spec_delta import descriptor, expand as expand_spec_delta, INSTRUCTION as DELTA_INSTRUCTION
from .feature_spec_metadata import repair_spec_metadata
from .feature_frozen_references import reference_catalog, expand_frozen_references, repair_reference_metadata
from .feature_accepted_metadata import capture, restore as restore_accepted_metadata
from .feature_audit_history import save_history
from .narrow_type_evidence_binding import content_digest
from plugins.development_quality.src.audit_schedule import audit_decision


class QualityChat:
    def __init__(self, transport, work, *, expected=None, require_baseline_expectations=False,
                 audit_mode='always'):
        audit_decision(audit_mode)
        self.audit_mode = audit_mode
        self.transport, self.work = transport, work
        self.expected = expected
        self.require_baseline_expectations = require_baseline_expectations
        self.policy = quality_contract({'action': 'policy'})['policy']
        self.events, self.retained, self.frozen = [], {}, []
        self.feedback = None
        self.pending = {}
        self.unaccepted = {}
        self.spec_witness = None
        self.cycle = 0
        self.accepted_metadata = None
        self.reference_pending = {}

    def needs_audit(self, role, *, scope=(), feedback=False, retained_campaign=False):
        decision = audit_decision(self.audit_mode, scope=scope,
            feedback=bool(feedback or self.feedback or self.pending or self.spec_witness
                or any(e['event'] == 'feedback_routed' for e in self.events)),
            retained_campaign=retained_campaign)
        self.record('audit_schedule', role=role, **decision)
        return decision['required']

    def freeze_specification(self, specification, *, goal, design, source_hashes=None):
        """Called only after native qualification (or its validated checkpoint)."""
        self.frozen = specification['tests']
        self.accepted_metadata = capture(specification, goal=goal, design=design,
            source_hashes=self.expected if source_hashes is None else source_hashes)

    def record(self, event, **fields):
        self.events.append({'event': event, 'cycle': self.cycle, **fields})
        save(self.work / 'autonomy.json', {'schema_version': 'feature_autonomy.v1',
             'scope': 'events inside this invocation; external task/fixture authorship is not independence',
             'events': self.events})

    def call(self, messages, config):
        messages = [dict(m) for m in messages]
        messages[0]['content'] = 'Return one JSON object only.\n' + messages[0]['content']
        role = config.provider_label.partition(':')[2]
        output_limit = self.policy.get('role_output_limits', {}).get(role)
        if (type(output_limit) is int and output_limit > 0 and
                (config.max_output_tokens is None or type(config.max_output_tokens) is int and config.max_output_tokens > 0)):
            config = replace(config, max_output_tokens=output_limit if config.max_output_tokens is None
                             else min(config.max_output_tokens, output_limit))
        if len(messages) == 2:
            payload = json.loads(messages[1]['content'])
            feedback = payload.get('quality_contract_feedback')
            if role == 'spec_writer' and feedback and 'historical_audits' in feedback:
                payload['quality_contract_feedback'] = {
                    key: value for key, value in feedback.items() if key != 'historical_audits'}
                payload['quality_contract_feedback']['historical_audits_digest'] = content_digest(
                    feedback['historical_audits'])
                messages[1]['content'] = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            payload, count = compact_test_references(payload)
            if count:
                messages[1]['content'] = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
                messages[0]['content'] += ('\nInput tests with content_reference contain the exact code '
                    'of the test with the same path in the named earlier field. '
                    'References are hash-bound and lossless. Read that complete code. Return full literal test '
                    'contents in output except explicitly authorized immutable_test_refs '
                    'for a SpecWriter response.')
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

    def audit_specification(self, payload, config):
        """Repair an invalid auditor mapping at its owner, never via test edits."""
        for attempt in range(self.policy['max_format_repairs'] + 1):
            audit = self.call([{'role': 'system', 'content': self.policy['spec_auditor']},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}], config)
            if not payload.get('baseline_assertion_inventory'):
                return audit
            errors = quality_contract({'action': 'validate_assertion_review',
                'artifact': payload['specification'], 'audit': audit,
                'frozen_paths': payload['accepted_test_paths']})['issues']
            if not errors:
                return audit
            self.record('audit_response_repair_requested', owner='spec_auditor', issues=errors)
            save(self.work / f'invalid-spec-audit-{self.cycle}-{len(self.events)}.json',
                 {'audit': audit, 'issues': errors, 'grants_approval': False})
            payload = {**payload, 'audit_response_feedback': {'previous_audit': audit, 'issues': errors,
                'instruction': self.policy['audit_response_repair']}}
        raise ValueError('quality_audit_response_invalid')

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
            save_history(self.work, binding, pending['feedback'].get('historical_audits', []))
        elif pending:
            self.pending.pop(role)
        if self.feedback:
            payload['quality_feedback'] = self.feedback
        instruction = messages[0]['content'] + '\n' + self.policy.get(role, '')
        if role == 'spec_writer':
            payload['specification_authority'] = {
                'immutable_paths': [t['path'] for t in self.frozen],
                'rejected_drafts_are_accepted': False}
            instruction += ('\nOnly tests in specification_authority.immutable_paths are accepted and frozen. '
                'Other tests in feedback.rejected_spec or previous unaccepted drafts remain editable, '
                'including incorrect preservation expectations exposed by native baseline. '
                'A test does not become immutable by appearing in an earlier draft or failing qualification. '
                'Correct its test/fixture error without changing production behavior to satisfy it.')
        reference_feedback = self.reference_pending.get(role)
        if reference_feedback and reference_feedback['binding'] == binding:
            payload['frozen_reference_feedback'] = reference_feedback['feedback']
        else:
            self.reference_pending.pop(role, None)
        if role == 'spec_writer' and self.frozen:
            payload['immutable_previous_tests'] = self.frozen
            payload['immutable_test_refs'] = reference_catalog(self.frozen)
            instruction += ('\nRetain these prior accepted tests byte-for-byte; return them unchanged '
                            'plus separate new files for uncovered cases. Do not replace old tests. '
                            'For each unchanged test, prefer the exact object from immutable_test_refs '
                            'instead of regenerating its content. Runtime expands only matching path/hash '
                            'references; new or changed tests require literal content. '
                            'Place references inside tests, or in a separate immutable_test_refs list '
                            'without duplicating those paths in tests. '
                            'Include case_plan covering the complete merged suite.')
            if self.accepted_metadata and self.accepted_metadata['binding'] == binding:
                payload['immutable_baseline_expectations'] = self.accepted_metadata['baseline_expectations']
                payload['immutable_case_plan'] = self.accepted_metadata['case_plan']
                instruction += ('\nRuntime retains immutable_baseline_expectations and immutable_case_plan '
                    'for unchanged accepted tests. You may omit those existing rows; provide both fields '
                    'for all NEW tests. '
                    'Do not regenerate accepted metadata. Runtime restores its exact qualified values '
                    'before the complete merged suite receives fresh audit and native qualification. '
                    'The current plugin policy explicitly permits correction of invalid legacy '
                    'case-plan labels only; baseline predictions and all other fields stay frozen.')
        for ordinal in range(self.policy['max_format_repairs'] + 1):
            if role == 'spec_writer':
                base = descriptor(payload)
                if base:
                    payload['specification_delta_base'] = base
                else:
                    payload.pop('specification_delta_base', None)
            restored = self.unaccepted.pop(role, None)
            if restored and restored['binding'] != binding:
                raise ValueError('quality_unaccepted_proposal_binding_changed')
            value = restored['proposal'] if restored else self.call([{'role': 'system', 'content': instruction + (
                DELTA_INSTRUCTION if role == 'spec_writer' and base else '')},
                               {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}], config)
            if value.get('status') != 'ready' or role not in ('analyzer', 'architect', 'spec_writer'):
                return value
            if role == 'analyzer':
                normalized = quality_contract({'action': 'repair_citations',
                    'artifact': value, 'sources': payload.get('sources', [])})
                if normalized['changes']:
                    save(self.work / f'citation-metadata-{self.cycle}-{ordinal}.json', {
                        **normalized, 'original': value, 'binding': binding,
                        'sources': payload.get('sources', [])})
                    value = normalized['artifact']
                    self.record('citation_metadata_repaired', changes=normalized['changes'], grants_approval=False)
            if role == 'spec_writer':
                try:
                    expanded = expand_spec_delta(value, payload)
                except ValueError as exc:
                    payload['specification_delta_feedback'] = {'reason': str(exc),
                        'rejected_output': value, 'instruction': 'Correct the explicit delta using the exact base descriptor. No edit was accepted.'}
                    self.record('feedback_routed', owner=role, phase='spec_delta', reason=str(exc))
                    continue
                if expanded is not value:
                    save(self.work / f'spec-delta-{self.cycle}-{ordinal}.json', {
                        'original': value, 'base': base, 'expanded': expanded, 'grants_approval': False})
                    self.record('spec_delta_expanded', base_digest=base['base_digest'], grants_approval=False)
                    value = expanded
                payload.pop('specification_delta_feedback', None)
                original = value
                value, reference_changes = repair_reference_metadata(value, self.frozen)
                if reference_changes:
                    save(self.work / f'frozen-reference-metadata-{self.cycle}-{ordinal}.json', {
                        'original': original, 'changes': reference_changes, 'grants_approval': False,
                        'frozen_catalog': reference_catalog(self.frozen)})
                    self.record('frozen_reference_metadata_repaired', changes=reference_changes, grants_approval=False)
                try:
                    value, count = expand_frozen_references(value, self.frozen, allow_separate=True)
                except ValueError as exc:
                    if str(exc) not in ('quality_stale_frozen_reference', 'quality_invalid_frozen_reference'):
                        raise
                    feedback = {'reason': str(exc), 'rejected_output': value,
                        'instruction': 'Use the exact immutable_test_refs path/hash for unchanged accepted tests, or their exact full text. Do not invent hashes or change frozen tests.'}
                    payload['frozen_reference_feedback'] = feedback
                    self.reference_pending[role] = {'binding': binding, 'feedback': feedback}
                    self.record('feedback_routed', owner=role, phase='output_reference', feedback=feedback)
                    continue
                self.reference_pending.pop(role, None)
                payload.pop('frozen_reference_feedback', None)
                if count:
                    save(self.work / f'frozen-refs-{self.cycle}-{ordinal}.json', {
                         'original': original, 'expanded': value, 'references': count,
                         'frozen_catalog': reference_catalog(self.frozen), 'grants_approval': False})
                    self.record('frozen_tests_referenced', count=count, grants_approval=False)
                value, changes = repair_spec_metadata(value, self.expected,
                    self.work / f'spec-metadata-{self.cycle}-{ordinal}.json')
                if changes:
                    self.record('spec_metadata_repaired', changes=changes, grants_approval=False)
                original = value
                value, changes = restore_accepted_metadata(value, self.accepted_metadata, binding,
                                                          allow_label_correction=True)
                if changes:
                    save(self.work / f'accepted-metadata-{self.cycle}-{ordinal}.json', {
                        'original': original, 'changes': changes, 'binding': binding,
                        'accepted': self.accepted_metadata, 'grants_approval': False})
                    self.record('accepted_metadata_reused', nodes=[r['node'] for r in changes], grants_approval=False)
            admission = quality_contract({'action': 'validate', 'role': role, 'artifact': value,
                                          'sources': payload.get('sources', [])})
            issues = admission['issues']
            structurally_valid = admission.get('semantic_audit_ready', not issues)
            if role == 'spec_writer':
                baseline_issues = quality_contract({'action': 'validate_baseline_expectations',
                    'artifact': value, 'goal': payload['goal'], 'sources': payload.get('sources', []),
                    'required': self.require_baseline_expectations})['issues']
                issues.extend(baseline_issues)
                structurally_valid = structurally_valid and not baseline_issues
            previous = payload.get('quality_contract_feedback')
            case_continuity = None
            if role == 'spec_writer' and previous and structurally_valid:
                case_continuity = quality_contract({'action': 'compare_draft',
                    'previous': previous['rejected'], 'current': value})
                if case_continuity['unexplained']:
                    issues.append({'draft_case_continuity': case_continuity})
            if role == 'spec_writer' and self.frozen:
                submitted = {t['path']: t['content'] for t in value.get('tests', [])}
                mismatches = frozen_test_mismatches(self.frozen, submitted)
                if mismatches:
                    issues.append({'immutable_test_mismatches': mismatches})
            if (role == 'architect' and not issues and self.needs_audit('design_auditor',
                    scope=value.get('scope', ()), feedback=bool(previous or ordinal))):
                audit = self.call([{'role': 'system', 'content': self.policy['design_auditor']},
                    {'role': 'user', 'content': json.dumps({'goal': payload['goal'], 'sources': payload['sources'],
                         'analysis': payload.get('artifacts', {}).get('analyzer'), 'design': value}, ensure_ascii=False, separators=(',', ':'))}],
                    replace(config, provider_label='quality:design_auditor'))
                save(self.work / f'design-audit-{self.cycle}-{ordinal}.json', audit)
                if audit.get('decision') != 'approve':
                    issues.append({'design_audit': audit})
            if role == 'spec_writer' and not issues and self.spec_witness:
                issues.extend(self.spec_witness(value))
            if (role == 'spec_writer' and structurally_valid
                    and not any('immutable_test_mismatches' in issue for issue in issues)
                    and (not self.spec_witness or not issues)
                    and self.needs_audit('spec_auditor',
                        scope=payload.get('artifacts', {}).get('architect', {}).get('scope', ()),
                        feedback=bool(issues or previous or ordinal or self.frozen))):
                assertion_inventory = (quality_contract({'action': 'assertion_inventory',
                    'artifact': value, 'frozen_paths': [t['path'] for t in self.frozen]})['assertion_inventory']
                    if self.require_baseline_expectations else None)
                audit = self.audit_specification({'goal': payload['goal'],
                        'accepted_metadata_contract': 'qualified_label_repair.v1',
                        'frozen_reference_contract': 'separate_frozen_refs.v1',
                        'execution_stage': 'specification_audit_before_native_qualification',
                        'sources': payload['sources'], 'design': payload.get('artifacts', {}).get('architect'),
                        'previous_unaccepted_draft': {k: v for k, v in previous.items()
                            if k != 'historical_audits'} if previous else None,
                        'omitted_previous_draft_files': missing_draft_files(previous['rejected'], value) if previous else [],
                        'draft_case_continuity': case_continuity,
                        'known_admission_issues': issues,
                        'accepted_test_paths': [t['path'] for t in self.frozen],
                        'prior_audit_issues': previous.get('prior_audit_issues', []) if previous else [],
                        'historical_audits': previous.get('historical_audits', []) if previous else [],
                        'review_counterexample_context': self.feedback,
                        'baseline_assertion_inventory': assertion_inventory,
                        'specification': value},
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
