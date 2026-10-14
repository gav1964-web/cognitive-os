"""Bind greenfield specification, bounded generator and observed delivery evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def bind_implementation(spec, preview):
    contract = spec.get('primary_contract', {})
    expected = contract.get('delivery_recipe', {})
    plan = preview.get('implementation_plan', {})
    recipe = plan.get('operation_recipe', {})
    checks = {
        'spec_ready': spec.get('status') == 'ok',
        'greenfield_handoff': spec.get('implementation_handoff', {}).get('mode') == 'greenfield_project',
        'bounded_plan': preview.get('status') == 'planned' and plan.get('status') == 'ready',
        'explicit_recipe': bool(expected) and all(expected.get(k) for k in ('interface_contract', 'transform')),
        'recipe_matches': bool(expected) and all(recipe.get(k) == v for k, v in expected.items()),
        'interface_matches': plan.get('interface_contract', {}).get('id') == contract.get('name'),
        'acceptance_declared': bool(contract.get('acceptance_check_ids')),
    }
    return {'artifact_type': 'GreenfieldImplementationHandoff', 'role': 'implementer',
            'status': 'ready' if all(checks.values()) else 'blocked', 'checks': checks,
            'spec_sha256': digest(spec), 'implementation_plan_sha256': digest(plan),
            'implementation_plan': plan,
            'test_plan': {'artifact_type': 'GreenfieldTestPlan', 'role': 'tester',
                'acceptance_check_ids': contract.get('acceptance_check_ids', []),
                'required_files': preview.get('files', []), 'require_nonempty_pytest': True,
                'spec_sha256': digest(spec)}}


def file_inventory(project):
    return {p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in project.rglob('*') if p.is_file()
            and not any(part.startswith('.') or part == '__pycache__'
                        for part in p.relative_to(project).parts)}


def review_delivery(spec, handoff, execution, verification, project, before):
    plan = handoff['test_plan']
    observed = verification.get('acceptance', {}).get('checks', [])
    ids = [row.get('id') for row in observed]
    checks = {
        'spec_binding': handoff['spec_sha256'] == digest(spec),
        'plan_binding': handoff['implementation_plan_sha256'] == digest(execution.get('implementation_plan', {})),
        'generator_verified': execution.get('status') == 'sandbox_verified'
            and execution.get('verification', {}).get('status') == 'passed',
        'pytest_passed': verification.get('pytest', {}).get('returncode') == 0
            and verification.get('pytest', {}).get('passing', 0) > 0,
        'acceptance_complete': len(ids) == len(set(ids)) and set(ids) == set(plan['acceptance_check_ids'])
            and bool(ids) and all(row.get('passed') is True for row in observed),
        'external_passed': verification.get('status') == 'passed'
            and verification.get('acceptance', {}).get('status') == 'passed',
        'required_files_present': bool(plan['required_files'])
            and all(name in before for name in plan['required_files']),
        'source_unchanged_by_verification': file_inventory(project) == before,
    }
    return {'artifact_type': 'GreenfieldDeliveryReview', 'role': 'reviewer',
            'status': 'approved' if all(checks.values()) else 'request_rework',
            'checks': checks, 'handoff_sha256': digest(handoff),
            'verification_sha256': digest(verification), 'files': before,
            'scope': 'Bounded contract delivery review; not independent product certification'}


def validate_output(root, output):
    output = Path(output).absolute()
    for path in (output, *output.parents):
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('linked_output_path')
    if not output.resolve().is_relative_to(root.resolve() / 'artifacts'):
        raise ValueError('greenfield_output_must_be_under_artifacts')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('greenfield_requires_empty_output')
    return output.resolve()
