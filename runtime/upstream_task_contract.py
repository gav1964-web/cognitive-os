"""Source-bound problem framing; supplied requirements are not discovered facts."""
from __future__ import annotations

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import owned_path
from .python_overload_resolution import implementation_candidates


def normalize_task_contract(value: dict) -> dict:
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 100_000:
        raise ValueError('task_contract_size_limit')
    if not isinstance(value, dict) or value.get('schema_version') != 'upstream_task_contract.v1':
        raise ValueError('invalid_upstream_task_contract')
    if value.get('origin') not in {'user_supplied', 'assistant_supplied', 'assistant_authored_development_fixture', 'model_proposal'}:
        raise ValueError('task_origin_required')
    if value.get('change_kind') not in {'defect', 'feature', 'architecture', 'ambiguous'}:
        raise ValueError('task_change_kind_required')
    rows = value.get('requirements')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
        raise ValueError('bounded_requirements_required')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
            raise ValueError('unique_requirement_ids_required')
        ids.add(row['id'])
        if not isinstance(row.get('statement'), str) or not row['statement'].strip() or len(row['statement']) > 4000:
            raise ValueError('requirement_statement_required')
        targets = row.get('targets', [])
        if not isinstance(targets, list) or len(targets) > 16 or any(not isinstance(t, str) for t in targets):
            raise ValueError('bounded_requirement_targets_required')
        examples = row.get('acceptance_examples', [])
        if not isinstance(examples, list) or len(examples) > 16 or any(not isinstance(e, dict) for e in examples):
            raise ValueError('bounded_acceptance_examples_required')
    constraints = value.get('constraints', [])
    if not isinstance(constraints, list) or len(constraints) > 32:
        raise ValueError('bounded_constraints_required')
    for row in constraints:
        if not isinstance(row, dict) or not isinstance(row.get('key'), str) or not row['key'] or 'value' not in row:
            raise ValueError('explicit_constraint_key_and_value_required')
    result = {k: deepcopy(value[k]) for k in ('schema_version', 'origin', 'change_kind', 'requirements')}
    result['constraints'] = deepcopy(constraints)
    result['contract_digest'] = content_digest(result)
    if value.get('contract_digest') and value['contract_digest'] != result['contract_digest']:
        raise ValueError('task_contract_digest_mismatch')
    return result


def analyze_task_contract(project: Path, contract: dict) -> dict:
    contract = normalize_task_contract(contract)
    facts, unresolved = [], []
    targets = list(dict.fromkeys(t for r in contract['requirements'] for t in r.get('targets', [])))
    for target in targets:
        try:
            path_text, separator, symbol = target.partition(':')
            if not separator or not symbol or not path_text.endswith('.py'):
                raise ValueError('exact_python_symbol_required')
            path = owned_path(project.resolve(), path_text)
            if path.name.startswith('.env') or path.name == 'config.json' or path.stat().st_size > 1_000_000:
                raise ValueError('unsupported_source')
            data = path.read_bytes()
            tree = ast.parse(data.decode('utf-8-sig'))
            scope, found = tree.body, None
            for name in symbol.split('.'):
                nodes = [n for n in scope if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
                nodes = implementation_candidates(tree, nodes)
                if len(nodes) != 1:
                    raise ValueError('missing_or_ambiguous_symbol')
                found, scope = nodes[0], nodes[0].body
            facts.append({'target': target, 'path': path_text, 'file_sha256': hashlib.sha256(data).hexdigest(),
                'line': found.lineno, 'origin': 'ast_source_observation',
                'claim': 'The requested symbol exists; behavior and root cause are not established by this observation.'})
        except (OSError, ValueError, SyntaxError, UnicodeError):
            unresolved.append({'target': target, 'reason': 'source_target_unverified'})
    conflicts = []
    seen = {}
    for item in contract['constraints']:
        key, value = item['key'], content_digest(item['value'])
        if key in seen and seen[key] != value:
            conflicts.append(key)
        seen[key] = value
    if not targets:
        unresolved.append({'reason': 'change_scope_not_supplied_or_discovered'})
    if contract['change_kind'] == 'ambiguous' and not conflicts:
        unresolved.append({'reason': 'ambiguous_request_requires_clarification'})
    body = {'schema_version': 'upstream_task_analysis.v1', 'contract_digest': contract['contract_digest'],
        'status': 'needs_clarification' if conflicts or unresolved else 'source_bound',
        'requirements_origin': contract['origin'], 'source_facts': facts,
        'conflicting_constraints': sorted(set(conflicts)), 'unresolved': unresolved,
        'hypotheses': [], 'causal_diagnosis': 'not_established',
        'semantic_requirement_validation': 'not_measured', 'execution_authorized': False}
    body['analysis_digest'] = content_digest(body)
    return body


def task_analysis_current(project: Path, contract: dict, analysis: dict) -> bool:
    # Recompute observations instead of accepting claimed hashes or a caller's ready flag.
    try:
        return analysis == analyze_task_contract(project, contract)
    except (ValueError, TypeError):
        return False
