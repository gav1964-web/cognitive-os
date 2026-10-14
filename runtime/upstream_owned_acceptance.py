"""Source-bound plugin acceptance on authorized copies; domain-neutral plumbing."""
import ast
import hashlib
import json
import sys
from pathlib import Path

from .competency_knowledge import invoke_knowledge
from .native_failure_acceptance import _probe
from .narrow_type_evidence_binding import content_digest
from .stage_finalization_workspace import inventory, owned_path, snapshot
from .upstream_requested_acceptance import test_outcome
from .upstream_task_contract import normalize_task_contract


def prepare_owned_acceptance(project, contract, plan, work_dir, *, authorized=False, root=None):
    if not authorized:
        raise ValueError('explicit_acceptance_execution_authorization_required')
    project, work = Path(project).resolve(), Path(work_dir).resolve()
    if work.exists() or work.is_relative_to(project) or project.is_relative_to(work):
        raise ValueError('fresh_external_acceptance_directory_required')
    contract = normalize_task_contract(contract)
    before = inventory(project)
    source_path = owned_path(project, plan['seed_source']['path'])
    data = source_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != plan['seed_source']['sha256']:
        raise ValueError('acceptance_seed_source_changed')
    payload = plan['payload']
    constants = [n.value for n in ast.walk(ast.parse(data.decode('utf-8'))) if isinstance(n,ast.Constant)]
    if not isinstance(payload.get('seed'), str) or payload['seed'] not in constants:
        raise ValueError('acceptance_seed_not_present_in_source')
    requirement = next((r for r in contract['requirements'] if r['id'] == plan['requirement_id']), None)
    if requirement is None:
        raise ValueError('acceptance_requirement_required')
    result = invoke_knowledge(plan['capability'], payload, **({'root':Path(root)} if root else {}))
    rows = result.get('tests', [])
    receipt = {'schema_version':'owned_acceptance.v1','status':'not_applicable','plan':plan,
        'contribution':result,'source_inventory_digest':content_digest(before),
        'applicability_origin':'explicit_caller_selection','semantic_adequacy':'bounded_property_only',
        'source_apply':False}
    if result.get('status') != 'proposed':
        return receipt
    fields = result.get('source_binding_fields', [])
    if (not isinstance(fields, list) or len(fields) > 8 or
            any(not isinstance(key, str) or not isinstance(payload.get(key), str)
                or payload[key] not in constants for key in fields)):
        raise ValueError('acceptance_example_not_present_in_source')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValueError('bounded_owned_acceptance_tests_required')
    names = [r['name'] for r in rows]
    if len(set(names)) != len(names) or any(not n.isidentifier() or not n.startswith('test_') for n in names):
        raise ValueError('distinct_native_test_names_required')
    source = '\n\n'.join(r['source'] for r in rows)
    tree = ast.parse(source)
    if len(source)>60000 or [n.name for n in tree.body if isinstance(n,ast.FunctionDef)] != names or len(tree.body)!=len(names):
        raise ValueError('ordinary_owned_test_functions_required')
    test_path = 'test_cos_owned_acceptance.py'
    if test_path in before:
        raise ValueError('owned_acceptance_path_already_exists')
    output = work/'project'
    snapshot(project, output, before)
    (output/test_path).write_text(source+'\n',encoding='utf-8')
    augmented = inventory(output)
    nodes = [test_path+'::'+name for name in names]
    probes = [_probe(output,work/f'baseline-{i}',nodes,[],60,Path(sys.executable),collect_nodeids=True) for i in range(2)]
    outcomes = [[test_outcome(p,n) for n in nodes] for p in probes]
    valid = (all(p['returncode'] in (0,1) and p.get('selected_nodeids') == nodes for p in probes)
             and outcomes[0] == outcomes[1] and all(o in ('passes','fails') for o in outcomes[0])
             and not any(r.get('failure_message','').startswith(('ImportError','ModuleNotFoundError','NameError'))
                         for p in probes for r in p.get('test_reports',[]))
             and probes[0].get('intake_signature') == probes[1].get('intake_signature')
             and inventory(project)==before and inventory(output)==augmented)
    required = [row.get('required_baseline_outcome') for row in rows]
    if any(value not in (None, 'passes', 'fails') for value in required):
        raise ValueError('invalid_owned_baseline_obligation')
    valid = valid and all(expected is None or all(run[i] == expected for run in outcomes)
                          for i, expected in enumerate(required))
    for node, outcome in zip(nodes, outcomes[0]):
        requirement['acceptance_examples'].append({'kind':'native_test','nodeid':node,
            'expectation':'passes','baseline_expectation':outcome,'origin':'competency_property',
            'capability':plan['capability'],'plan_digest':content_digest(plan)})
    contract.pop('contract_digest')
    receipt.update(status='baseline_verified' if valid else 'not_verified',project=str(output),
        task_contract=normalize_task_contract(contract),probes=probes,
        source_unchanged=inventory(project)==before,generated_nodeids=nodes)
    receipt['digest']=content_digest(receipt)
    (work/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return receipt
