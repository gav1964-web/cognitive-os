"""Materialize the exact tested model bytes; never regenerate a replacement."""
from pathlib import Path

from .native_failure_acceptance import _validate
from .narrow_type_evidence_binding import content_digest
from .programmer_patch_synthesizer_common import _patch_result, _expected_files, _target_symbol
from .stage_finalization_workspace import inventory, snapshot, owned_path
from .upstream_model_delivery import AUTHORITY, validate_delivery_source, validate_delivery_intent


def model_delivery_mode(spec: dict, plan: dict) -> bool:
    for artifact in (spec, plan):
        intent = (artifact.get('implementation_delta') or {}).get('intent') or {}
        if (intent.get('model_delivery') is not None or intent.get('authority') == AUTHORITY
                or (intent.get('causal_comparison') or {}).get('candidate_origin') == 'llm_structured_proposal'):
            return True
    return False


def model_delivery_precheck(spec: dict, plan: dict) -> str | None:
    if not model_delivery_mode(spec, plan):
        return None
    try:
        expected = (spec.get('implementation_delta') or {}).get('intent') or {}
        actual = (plan.get('implementation_delta') or {}).get('intent') or {}
        validate_delivery_intent(expected)
        validate_delivery_intent(actual)
        if expected['model_delivery'].get('task_contract_digest') or spec.get('task_contract') is not None:
            from .upstream_requested_review import requested_change_checks
            if not all(r['passed'] for r in requested_change_checks(spec, {})):
                raise ValueError('model_delivery_requested_requirements_invalid')
        if any(expected.get(k) != actual.get(k) for k in (
                'model_delivery', 'causal_comparison', 'failure_evidence_packet', 'target_symbol',
                'operator_id', 'allowed_operator_ids', 'authority', 'repair_grounding')):
            raise ValueError('model_delivery_spec_plan_mismatch')
    except (ValueError, KeyError, TypeError):
        return 'model_delivery_spec_plan_invalid'
    return None


def model_delivery_package(*, execution_dir: Path, project_dir: Path,
                           implementation_plan: dict, test_plan: dict) -> dict:
    try:
        delta = implementation_plan.get('implementation_delta') or {}
        intent = delta.get('intent') or {}
        if delta.get('status') != 'ready':
            raise ValueError('model_delivery_delta_not_ready')
        before, original = validate_delivery_source(project_dir, intent)
        ticket = intent['model_delivery']
        if ticket.get('task_contract_digest') and not all(ticket.get(k) for k in (
                'requested_change_digest', 'requested_acceptance_digest')):
            raise ValueError('model_delivery_requested_evidence_required')
        target = ticket['target']
        path = target.partition(':')[0]
        if _target_symbol(implementation_plan) != target or _expected_files(implementation_plan) != [path]:
            raise ValueError('model_delivery_plan_scope_mismatch')
        acceptance = test_plan.get('executable_acceptance') or {}
        _validate(acceptance, before)
        if acceptance.get('packet') != intent['failure_evidence_packet'] or acceptance.get('target') != target:
            raise ValueError('model_delivery_test_packet_mismatch')
        sandbox = execution_dir.resolve() / 'model_delivery' / 'project'
        source = project_dir.resolve()
        if sandbox.exists() or sandbox.is_relative_to(source) or source.is_relative_to(sandbox):
            raise ValueError('model_delivery_requires_fresh_external_copy')
        snapshot(project_dir, sandbox, before)
        replacement = ticket['replacement_source']
        owned_path(sandbox, path).write_bytes(replacement.encode('utf-8'))
        if content_digest(inventory(sandbox)) != ticket['patched_inventory_digest'] or inventory(project_dir) != before:
            raise ValueError('model_delivery_materialization_changed')
        return _patch_result(recipe={'status': 'prepared', 'reason': 'prevalidated_model_candidate_materialized'},
            sandbox_project=sandbox, path_text=path, target=target, original=original, patched=replacement,
            operation={'artifact_type': 'PatchOperation', 'kind': 'replay_selected_model_candidate',
                'target': target, 'file': path, 'authority': ticket['authority'],
                'delivery_digest': ticket['delivery_digest'], 'candidate_id': ticket['candidate_id'],
                'comparison_digest': ticket['comparison_digest']})
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        return {'status': 'blocked', 'reason': str(exc), 'patches': []}
