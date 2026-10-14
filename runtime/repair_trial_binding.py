"""Explicitly bind an internal repair trial to an immutable observed failure.

This derived packet is not a new native observation. Nomination constrains the
patch location; independent authorization and behavioral replay remain required.
"""
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest
from .project_failure_evidence_packet import (
    is_complete_failure_evidence_packet, _target_source, evidence_packet_digest,
)
from .repair_target_nomination import validate_nomination, nomination_file_hash

SCHEMA = 'repair_trial_packet.v1'
COPIED = ('failure_signature', 'failure_kind', 'failing_nodeids', 'observed_failure',
          'assertion_evidence', 'test_sources', 'helper_call_provenance',
          'project_inventory_digest', 'reproduction', 'checks')


def observed_packet(packet):
    return packet['observation_packet'] if packet.get('schema_version') == SCHEMA else packet


def _payload(nomination):
    return {'target': nomination['repair_target'], 'context_digest': nomination['context_digest'],
            'file_sha256': nomination['file_sha256'], 'reason': nomination['reason']}


def build_repair_trial_packet(*, project, observation: dict, bundle: dict) -> dict:
    if observation.get('schema_version') != 'project_failure_evidence_packet.v1':
        raise ValueError('original_observation_packet_required')
    if set(bundle) != {'nomination', 'trace', 'context'}:
        raise ValueError('repair_nomination_bundle_schema')
    nomination = bundle['nomination']
    verified = validate_nomination(_payload(nomination), project=project, packet=observation,
                                  trace=bundle['trace'], context=bundle['context'])
    if nomination != verified:
        raise ValueError('repair_nomination_mismatch')
    source = _target_source(project, nomination['repair_target'])
    if not source or source['file_sha256'] != nomination['file_sha256']:
        raise ValueError('repair_source_mismatch')
    packet = {k: deepcopy(observation[k]) for k in COPIED}
    packet.update(artifact_type='ProjectRepairTrialPacket', schema_version=SCHEMA,
        status='complete', target=nomination['repair_target'], target_source=source,
        observed_target=observation['target'], observation_packet=deepcopy(observation),
        repair_nomination=deepcopy(bundle), execution_authorized=False, source_changes=False)
    packet['packet_digest'] = evidence_packet_digest(packet)
    if not is_repair_trial_packet(packet, target=packet['target']):
        raise ValueError('repair_trial_packet_invalid')
    return packet


def is_repair_trial_packet(packet: dict, *, target: str) -> bool:
    try:
        observation, bundle = packet['observation_packet'], packet['repair_nomination']
        nomination, trace, context = bundle['nomination'], bundle['trace'], bundle['context']
        return bool(
            packet['artifact_type'] == 'ProjectRepairTrialPacket' and packet['schema_version'] == SCHEMA
            and packet['status'] == 'complete' and packet['target'] == target
            and packet['execution_authorized'] is False and packet['source_changes'] is False
            and observation.get('schema_version') == 'project_failure_evidence_packet.v1'
            and is_complete_failure_evidence_packet(observation, target=observation['target'])
            and packet['observed_target'] == observation['target'] != target
            and all(packet[k] == observation[k] for k in COPIED)
            and evidence_packet_digest(packet) == packet['packet_digest']
            and nomination['schema_version'] == 'repair_target_nomination.v1'
            and nomination['status'] == 'advisory_nomination' and nomination['repair_target'] == target
            and nomination['observed_target'] == observation['target']
            and nomination['execution_authorized'] is nomination['source_apply'] is nomination['root_cause_proven'] is False
            and nomination['observation_packet_digest'] == observation['packet_digest']
            and nomination['nomination_digest'] == content_digest({k: v for k, v in nomination.items() if k != 'nomination_digest'})
            and nomination['context_digest'] == context['context_digest']
            and context['context_digest'] == content_digest({k: v for k, v in context.items() if k != 'context_digest'})
            and nomination['trace_digest'] == context['trace_digest'] == trace['trace_digest']
            and trace['trace_digest'] == content_digest({k: v for k, v in trace.items() if k != 'trace_digest'})
            and trace['observation_packet_digest'] == context['observation_packet_digest'] == observation['packet_digest']
            and trace['project_inventory_digest'] == context['project_inventory_digest'] == observation['project_inventory_digest']
            and target in context['eligible_targets']
            and nomination['file_sha256'] == nomination_file_hash(context, target) == packet['target_source']['file_sha256']
            and packet['target_source']['path'] + ':' + packet['target_source']['symbol'] == target
            and ((context['schema_version'] == 'repair_function_nomination_context.v1'
                  and trace['schema_version'] == 'repair_function_trace.v1'
                  and any(r['target'] == target and r['file_sha256'] == nomination['file_sha256']
                          for r in context['methods']))
                 or (context['schema_version'] == 'repair_target_nomination_context.v1'
                     and target.partition(':')[0] == observation['target'].partition(':')[0])))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def validate_repair_trial_source(project, packet):
    if packet.get('schema_version') != SCHEMA:
        return
    if build_repair_trial_packet(project=project, observation=packet['observation_packet'],
                                  bundle=packet['repair_nomination']) != packet:
        raise ValueError('repair_trial_source_or_binding_changed')


def bind_repair_diagnosis(diagnosis: dict, *, project, bundle: dict) -> dict:
    result = deepcopy(diagnosis)
    issues = [i for i in result.get('issues', []) if i.get('failure_specific_reducer_required')]
    if len(issues) != 1:
        raise ValueError('single_observed_failure_issue_required')
    issue = issues[0]
    observation = issue['failure_evidence_packet']
    failures = issue.get('failure_evidence') or []
    if (issue.get('affected_targets') != [observation['target']] or len(failures) != 1
            or failures[0].get('target') != observation['target']
            or failures[0].get('failure_signature') != observation['failure_signature']
            or failures[0].get('failing_nodeids') != observation['failing_nodeids']):
        raise ValueError('repair_observation_issue_mismatch')
    packet = build_repair_trial_packet(project=project, observation=observation, bundle=bundle)
    issue['observed_affected_targets'] = deepcopy(issue['affected_targets'])
    issue['affected_targets'] = [packet['target']]
    issue['failure_evidence_packet'] = packet
    # Historical failures and packet list retain observed API provenance.
    issue['repair_trial_packet_digest'] = packet['packet_digest']
    return result


def validate_repair_patch_scope(original: str, replacement: str, packet: dict):
    """Verify exact single-method bytes even if acceptance is called directly."""
    if packet.get('schema_version') != SCHEMA:
        return
    import ast
    import textwrap
    from .upstream_llm_candidates import _replacement
    scope = ast.parse(replacement).body
    for part in packet['target'].partition(':')[2].split('.'):
        matches = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == part]
        if len(matches) != 1:
            raise ValueError('repair_patch_target_not_unique')
        node = matches[0]
        scope = node.body
    function = ''.join(replacement.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    function = textwrap.dedent(function.replace('\r\n', '\n'))
    if _replacement(original, packet['target'], function) != replacement:
        raise ValueError('repair_patch_outside_nominated_method')
