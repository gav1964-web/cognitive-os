"""Compare bounded, explicitly authorized proposals on unchanged native tests.

Support means agreement with observed tests, not a uniquely proven root cause.
Candidate code executes only in trusted-code subprocess copies through Replay.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from .native_failure_acceptance import build_native_acceptance, run_native_acceptance, _validate
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, snapshot, changed_files, owned_path


def compare_causal_candidates(*, project: Path, packet: dict, candidates: list[dict],
                             work_dir: Path, authorized: bool = False,
                             candidate_origin: str = 'training_rule_proposal') -> dict:
    """Validate a bounded candidate set; never choose by candidate order."""
    if not authorized:
        raise ValueError('explicit_training_trial_authorization_required')
    if candidate_origin not in {'training_rule_proposal', 'llm_structured_proposal'}:
        raise ValueError('unsupported_candidate_origin')
    project, work_dir = project.resolve(), work_dir.resolve()
    if project.is_relative_to(work_dir) or work_dir.is_relative_to(project):
        raise ValueError('trial_output_must_be_outside_source_project')
    if not 1 <= len(candidates) <= 4 or len({r['id'] for r in candidates}) != len(candidates):
        raise ValueError('one_to_four_unique_candidates_required')
    before = inventory(project)
    target = packet.get('target', '')
    spec = {'contract_mode': 'failure_repair',
            'implementation_delta': {'intent': {'failure_evidence_packet': packet}},
            'acceptance_criteria': [{'id': f'AC-FAILURE-REPLAY-{i:03d}'}
                                    for i, _ in enumerate(packet.get('failing_nodeids', []), 1)]}
    contract = build_native_acceptance(spec, target)
    # Validate signed inventory, exact production path and native IDs before writes.
    _validate(contract, before)
    from .repair_trial_binding import SCHEMA, validate_repair_trial_source
    validate_repair_trial_source(project, packet)
    if packet.get('schema_version') == SCHEMA and candidate_origin != 'llm_structured_proposal':
        raise ValueError('nominated_repair_requires_bound_model_candidate')
    path_text = target.partition(':')[0]
    source = owned_path(project, path_text)
    # Validate the whole set before any candidate can execute.
    for candidate in candidates:
        if (candidate.get('origin') != candidate_origin
                or candidate.get('source_sha256') != before[path_text]
                or not isinstance(candidate.get('replacement_source'), str)):
            raise ValueError('source_bound_candidate_required')
        if len(candidate['replacement_source'].encode('utf-8')) > 1_000_000:
            raise ValueError('candidate_size_limit')
        if candidate_origin == 'llm_structured_proposal':
            from .upstream_llm_candidates import validate_model_candidate
            validate_model_candidate(candidate, packet, source.read_bytes().decode('utf-8'))
            preservation = candidate.get('provenance', {}).get('repair_design', {}).get('preservation_evidence')
            if preservation is not None:
                from .repair_preservation import validate_preservation
                validate_preservation(packet, preservation, project)
    attempts = []
    work = work_dir / ('causal-' + uuid.uuid4().hex[:10])
    work.mkdir(parents=True, exist_ok=False)
    fingerprints = set()
    for index, candidate in enumerate(candidates):
        encoded = candidate['replacement_source'].encode('utf-8')
        fingerprint = content_digest(candidate['replacement_source'])
        row = {k: deepcopy(v) for k, v in candidate.items() if k != 'replacement_source'}
        row['replacement_digest'] = fingerprint
        if fingerprint in fingerprints:
            row.update(outcome='duplicate_patch', evidence=None)
        elif encoded == source.read_bytes():
            row.update(outcome='no_change', evidence=None)
        else:
            candidate_root = work / f'candidate-{index}'
            snapshot(project, candidate_root, before)
            owned_path(candidate_root, path_text).write_bytes(encoded)
            evidence = run_native_acceptance(source_project=project, patched_project=candidate_root,
                                             contract=contract, work_dir=work / f'checks-{index}')
            checks = evidence['summary']['native_replay_checks']
            stable = all(checks.get(key) is True for key in (
                'source_packet_current', 'patch_scope_preserved', 'baseline_failure_repeated',
                'recorded_failure_reproduced', 'test_collection_preserved',
                'source_copies_unchanged', 'input_projects_unchanged'))
            outcome = 'supported_by_targeted_tests' if evidence['status'] == 'passed' else (
                'contradicted_by_targeted_tests' if stable and evidence['probes'][-1]['returncode'] == 1
                else 'inconclusive')
            row.update(outcome=outcome, evidence=evidence, patched_project=str(candidate_root))
            preservation = candidate.get('provenance', {}).get('repair_design', {}).get('preservation_evidence')
            if preservation is not None and outcome == 'supported_by_targeted_tests':
                from .repair_preservation import check_candidate_preservation
                check = check_candidate_preservation(project, candidate_root, packet, preservation,
                                                     work / f'preservation-{index}')
                row['preservation_check'] = check
                if check['status'] != 'passed':
                    row['outcome'] = ('contradicted_by_preservation_tests'
                        if check['same_cases'] and check['probe']['copy_unchanged'] and check['probe']['returncode'] == 1
                        else 'inconclusive')
        fingerprints.add(fingerprint)
        attempts.append(row)
        # Preserve every attempt, including failed or interrupted later comparisons.
        (work / 'attempts.json').write_text(json.dumps(attempts, indent=2), encoding='utf-8')
    supported = [r for r in attempts if r['outcome'] == 'supported_by_targeted_tests']
    uncertain = any(r['outcome'] in {'inconclusive', 'duplicate_patch', 'no_change'} for r in attempts)
    changed = changed_files(project, before)
    selected = supported[0] if len(supported) == 1 and not uncertain and not changed else None
    status = ('source_changed' if changed else 'ambiguous' if len(supported) > 1 else
              'inconclusive' if uncertain else 'selected_for_regression' if selected else 'no_supported_candidate')
    result = {'schema_version': 'upstream_causal_comparison.v1', 'status': status,
        'target': target, 'packet_digest': packet['packet_digest'],
        'source_inventory_digest': content_digest(before), 'source_changes': changed,
        'attempts': attempts, 'selected_candidate_id': selected['id'] if selected else None,
        'comparison_scope': ('provided_training_candidates_and_recorded_native_failures'
            if candidate_origin == 'training_rule_proposal' else 'provided_llm_candidates_and_recorded_native_failures'),
        'candidate_origin': candidate_origin,
        'root_cause_uniquely_proven': False, 'complete_native_regression': 'still_required',
        'independent_quality_score': None, 'source_apply': False, 'promotion_allowed': False,
        'receipt_path': str(work / 'comparison.json')}
    result['comparison_digest'] = content_digest(result)
    Path(result['receipt_path']).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
