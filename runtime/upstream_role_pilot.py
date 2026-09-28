"""Run six development cases and controlled substitutions through real role builders."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

from .architecture_decision_builder import build_architecture_decision
from .technical_spec_builder import build_technical_spec
from .role_project_analysis import analyze_role_project
from .upstream_role_audit import audit_upstream_roles, compare_upstream_variants
from .upstream_role_feedback import build_upstream_feedback
from .stage_finalization_workspace import inventory, owned_path, changed_files
from .narrow_type_evidence_binding import content_digest


def run_upstream_role_pilot(root: Path, *, manifest_path: str, references_path: str) -> dict:
    root = root.resolve()
    manifest = json.loads(owned_path(root, manifest_path).read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'upstream_role_scenarios.v1' or len(manifest.get('cases', [])) != 6:
        raise ValueError('six_development_scenarios_required')
    cases = manifest['cases']
    if len({c['id'] for c in cases}) != 6 or any(c.get('split') != 'development' for c in cases):
        raise ValueError('unique_development_cases_required')
    before = inventory(root)
    original_rows = []
    # Finish all original attempts before loading corrected diagnostic inputs.
    for case in cases:
        project = owned_path(root, case['project'])
        if inventory(project) != case['source_hashes']:
            raise ValueError('scenario_source_changed')
        start = time.monotonic()
        analysis = analyze_role_project(root=root, project_dir=project, goal=case['goal'],
                                        task_contract=case['task_contract'])['project_map_report']
        adr = build_architecture_decision(goal=case['goal'], project_report=analysis)
        spec = build_technical_spec(architecture_decision=adr)
        original_rows.append({'id': case['id'], 'analysis': analysis, 'architecture': adr,
                              'specification': spec, 'elapsed_seconds': time.monotonic() - start})
    reference = json.loads(owned_path(root, references_path).read_text(encoding='utf-8'))
    if reference.get('schema_version') != 'upstream_diagnostic_inputs.v1' or set(reference['cases']) != {c['id'] for c in cases}:
        raise ValueError('diagnostic_input_set_mismatch')
    results = []
    for case, original in zip(cases, original_rows):
        corrected = reference['cases'][case['id']]
        variants = {'original': original}
        analysis = deepcopy(original['analysis'])
        analysis['diagnostic_hypotheses'] = [{'statement': corrected['hypothesis'], 'origin': reference['origin'],
                                             'verification': 'not_independently_verified'}]
        start = time.monotonic()
        adr = build_architecture_decision(goal=case['goal'], project_report=analysis)
        spec = build_technical_spec(architecture_decision=adr)
        variants['corrected_analysis'] = {'analysis': analysis, 'architecture': adr,
                                          'specification': spec, 'elapsed_seconds': time.monotonic() - start}
        adr = deepcopy(original['architecture'])
        adr['design_proposal'] = {'steps': corrected['steps'], 'preserve': corrected['preserve'],
                                  'origin': reference['origin'], 'verification': 'not_independently_verified'}
        start = time.monotonic()
        variants['corrected_architecture'] = {'analysis': original['analysis'], 'architecture': adr,
            'specification': build_technical_spec(architecture_decision=adr), 'elapsed_seconds': time.monotonic() - start}
        for name, row in variants.items():
            intervention = [] if name == 'original' else [{'kind': name, 'origin': reference['origin']}]
            row['audit'] = audit_upstream_roles(task=case['task_contract'], analysis=row['analysis'],
                architecture=row['architecture'], specification=row['specification'], interventions=intervention)
            row['feedback'] = build_upstream_feedback(analysis=row['analysis'], architecture=row['architecture'],
                                                      specification=row['specification'])
            row['artifact_digest'] = content_digest({key: row[key] for key in ('analysis', 'architecture', 'specification')})
        results.append({'id': case['id'], 'kind': case['kind'], 'variants': variants,
                        'comparison': compare_upstream_variants(variants)})
    changed = changed_files(root, before)
    return {'schema_version': 'upstream_role_pilot.v1', 'status': 'completed' if not changed else 'source_changed',
        'scope': manifest['scope'], 'cases': results, 'source_inventory': before, 'source_changes': changed,
        'manifest_digest': content_digest(manifest), 'diagnostic_inputs_digest': content_digest(reference),
        'model_calls': 0, 'model_tokens': 0, 'assistant_cost': 'not_available_to_runner',
        'independent_quality_score': None, 'independent_judge': False,
        'summary': {'cases': len(results), 'variants': sum(len(r['variants']) for r in results),
            'original_requirements_preserved': sum(r['variants']['original']['audit']['checks']['requirements_preserved'] for r in results),
            'original_causal_diagnoses_verified': 0, 'implementation_executions': 0}}
