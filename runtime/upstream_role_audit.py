"""Attribute first-three-role outputs and measure explicit handoff properties."""
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest


def audit_upstream_roles(*, task: dict, analysis: dict, architecture: dict, specification: dict,
                         interventions: list[dict] | None = None) -> dict:
    artifacts = {'analyzer': analysis, 'architect': architecture, 'spec_writer': specification}
    fields = {
        'analyzer': {'summary': 'tool_observation', 'answers': 'static_analysis_and_templates',
                     'task_contract': task.get('origin', 'caller_supplied'), 'task_analysis': 'source_checks_and_explicit_constraints'},
        'architect': {'architecture_options': 'policy_proposal', 'chosen_option': 'policy_selection',
                      'fact_judgment_ledger': 'source_references_and_uncalibrated_policy_judgments',
                      'source_context': 'static_source_analysis', 'task_contract': 'inherited_requirement',
                      'open_questions': 'generated_followup', 'design_proposal': 'assistant_supplied_diagnostic_input'},
        'spec_writer': {'requirements': 'inherited_or_template_requirement',
                        'acceptance_criteria': 'supplied_examples_and_generated_templates',
                        'implementation_delta': 'configured_builder', 'task_handoff': 'handoff_completeness_checks'},
    }
    roles = {}
    for role, artifact in artifacts.items():
        claims = [{'path': key, 'origin': origin, 'content_digest': content_digest(artifact[key]),
                   'semantic_correctness': 'not_established_by_origin'}
                  for key, origin in fields[role].items() if key in artifact]
        roles[role] = {'artifact_status': artifact.get('status'), 'claims': claims,
                       'reasoning_provenance': deepcopy(artifact.get('reasoning_provenance')),
                       'quality_score': None, 'independent_quality_measured': False}
    requirements = task.get('requirements', [])
    spec_rows = specification.get('requirements', [])
    preserved = [r['id'] for r in requirements if any(
        row.get('id') == r['id'] and row.get('statement') == r['statement'] for row in spec_rows)]
    examples = specification.get('requested_acceptance_criteria', [])
    expected_examples = sum(len(r.get('acceptance_examples', [])) for r in requirements)
    retained_examples = sum(any(row.get('requirement_id') == r['id'] and row.get('example') == example
                                for row in examples)
                            for r in requirements for example in r.get('acceptance_examples', []))
    task_analysis = analysis.get('task_analysis') or {}
    authority = specification.get('task_handoff', {}).get('execution_authorized')
    verified_authority = False
    if authority is True and specification.get('requested_change'):
        from .upstream_requested_review import requested_change_checks
        verified_authority = all(r['passed'] for r in requested_change_checks(specification, {}))
    checks = {
        'requirements_preserved': len(preserved) == len(requirements) and bool(requirements),
        'acceptance_examples_preserved': retained_examples == expected_examples,
        'origin_disclosed': all(artifacts[r].get('reasoning_provenance') for r in artifacts),
        'conflict_blocks_handoff': (not task_analysis.get('conflicting_constraints') or
                                   specification.get('task_handoff', {}).get('status') == 'needs_clarification'),
        'no_unverified_design_authority': authority is False or verified_authority,
    }
    return {'schema_version': 'upstream_role_audit.v1', 'roles': roles, 'checks': checks,
            'requirements': {'total': len(requirements), 'preserved_ids': preserved},
            'examples': {'expected': expected_examples, 'retained': retained_examples},
            'metric_scope': 'explicit handoff retention and authority checks; not semantic role scores',
            'interventions': deepcopy(interventions or []), 'independent_judge': False}


def compare_upstream_variants(variants: dict) -> dict:
    original = variants['original']['audit']['checks']
    return {name: {'changed_checks': [key for key, value in row['audit']['checks'].items() if original.get(key) != value],
                   'interpretation': 'diagnostic input substitution; never a fresh independent attempt'}
            for name, row in variants.items() if name != 'original'}
