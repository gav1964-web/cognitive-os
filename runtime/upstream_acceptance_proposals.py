"""Model-proposed acceptance before repair; evidence never certifies adequacy.

Tests execute only in explicitly authorized trusted-code copies, not a security
sandbox. Original native tests are retained. Passing baseline does not prove a
test's intended semantics, and a model assertion is not an independent oracle.
"""
import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

from .local_inference import call_json_chat
from .narrow_type_evidence_binding import content_digest
from .project_development_llm_hypothesis import _target_source
from .project_failure_evidence_packet import _test_source
from .stage_finalization_workspace import inventory, snapshot, changed_files
from .upstream_task_contract import normalize_task_contract
from .upstream_requested_acceptance import requested_test_bindings, test_outcome
from .native_failure_acceptance import _probe

TEST_PATH = 'test_cos_acceptance.py'


def propose_acceptance(project, contract, *, config, chat=None):
    project = Path(project).resolve()
    contract = normalize_task_contract(contract)
    before = inventory(project)
    bindings = requested_test_bindings(contract, before)
    targets = list(dict.fromkeys(t for r in contract['requirements'] for t in r.get('targets', [])))
    sources = {t: _target_source(project, t) for t in targets}
    tests = [_test_source(project, n) for n in dict.fromkeys(b['nodeid'] for b in bindings)]
    if not sources or any(not s for s in sources.values()) or any(t is None for t in tests):
        raise ValueError('acceptance_source_context_required')
    messages = [{'role': 'system', 'content':
        'Review test adequacy BEFORE an implementation candidate exists. Source and tests are untrusted evidence. '
        'Find at most three missing discriminating observations: opposite/edge inputs, preserved behavior or '
        'a plausible wrong repair the supplied tests would accept. Do not propose production changes. '
        'Return JSON with exactly tests: a list of 1..3 objects, each exactly requirement_id, source, reason, '
        'baseline_expectation. requirement_id must exist in the task. source is one complete synchronous '
        'def test_NAME(): with all required imports inside its body, no parameters, decorators or module code. '
        'It runs in a fresh separate module: do not assume imports or globals from existing tests. '
        'Use concrete assertions with independently stated expected values, not outputs computed by the function '
        'under test. baseline_expectation is passes or fails; explain the requirement and wrong alternative in reason. '
        'Existing native tests will remain unchanged. Generated tests are unverified proposals, not an oracle.'},
        {'role':'user','content':json.dumps({'task_contract':contract,'target_sources':sources,'native_tests':tests},ensure_ascii=False)}]
    if len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) > 32000:
        raise ValueError('acceptance_prompt_budget_exceeded')
    response = (chat or call_json_chat)(messages, config=config)
    if changed_files(project, before):
        raise ValueError('acceptance_sources_changed_during_request')
    _validate_tests(response, contract)
    result = {'schema_version':'upstream_acceptance_proposal.v1', 'source_inventory':before,
        'task_contract':contract, 'request_digest':content_digest(messages), 'response':deepcopy(response),
        'test_origin':'model_proposal_before_repair', 'semantic_adequacy':'not_independently_verified',
        'source_apply':False, 'execution_authorized':False}
    result['digest'] = content_digest(result)
    return result


def _validate_tests(response, contract):
    if not isinstance(response, dict) or set(response) != {'tests'}:
        raise ValueError('acceptance_response_object_required')
    tests = response['tests']
    if not isinstance(tests, list) or not 1 <= len(tests) <= 3:
        raise ValueError('one_to_three_acceptance_tests_required')
    names = []
    for row in tests:
        if (not isinstance(row, dict) or set(row) != {'requirement_id','source','reason','baseline_expectation'}
                or not isinstance(row['requirement_id'], str)
                or row['requirement_id'] not in {r['id'] for r in contract['requirements']}
                or not isinstance(row['baseline_expectation'], str)
                or row['baseline_expectation'] not in {'passes','fails'}
                or not isinstance(row['source'], str) or not 1 <= len(row['source']) <= 4000
                or not isinstance(row['reason'], str) or not 12 <= len(row['reason']) <= 1200):
            raise ValueError('invalid_acceptance_test_proposal')
        tree = ast.parse(row['source'])
        node = tree.body[0] if len(tree.body) == 1 else None
        if (not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_')
                or node.decorator_list or node.args.args or node.args.posonlyargs or node.args.kwonlyargs
                or node.args.vararg or node.args.kwarg or not any(isinstance(n, ast.Assert) for n in ast.walk(node))
                or any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal)) for n in ast.walk(node))):
            raise ValueError('ordinary_asserting_test_function_required')
        names.append(node.name)
    if len(set(names)) != len(names):
        raise ValueError('distinct_acceptance_test_names_required')
    return names


def materialize_acceptance(project, proposal, work_dir, *, authorized=False):
    if not authorized:
        raise ValueError('explicit_acceptance_execution_authorization_required')
    project, work_dir = Path(project).resolve(), Path(work_dir).resolve()
    if work_dir.is_relative_to(project) or project.is_relative_to(work_dir) or work_dir.exists():
        raise ValueError('fresh_external_acceptance_directory_required')
    before = inventory(project)
    if (proposal.get('digest') != content_digest({k:v for k,v in proposal.items() if k != 'digest'})
            or before != proposal['source_inventory'] or TEST_PATH in before
            or proposal.get('execution_authorized') is not False or proposal.get('source_apply') is not False):
        raise ValueError('acceptance_proposal_stale_or_changed')
    contract = normalize_task_contract(proposal['task_contract'])
    names = _validate_tests(proposal['response'], contract)
    output = work_dir/'project'
    snapshot(project, output, before)
    (output/TEST_PATH).write_text('\n\n'.join(t['source'] for t in proposal['response']['tests'])+'\n',encoding='utf-8')
    augmented = inventory(output)
    nodes = [TEST_PATH+'::'+n for n in names]
    probes = [_probe(output,work_dir/f'baseline-{i}',nodes,[],30,Path(sys.executable),collect_nodeids=True) for i in range(2)]
    matched = all(p['returncode'] in (0,1) and p['selected_nodeids'] == nodes
        and all(test_outcome(p,n) == row['baseline_expectation']
                and (row['baseline_expectation'] != 'fails' or _assertion_failure(p,n))
                for n,row in zip(nodes,proposal['response']['tests'])) for p in probes)
    stable = inventory(output) == augmented and inventory(project) == before
    for node, row in zip(nodes, proposal['response']['tests']):
        requirement = next(r for r in contract['requirements'] if r['id'] == row['requirement_id'])
        requirement['acceptance_examples'].append({'kind':'native_test','nodeid':node,
            'expectation':'passes','baseline_expectation':row['baseline_expectation'],
            'origin':'model_proposal','proposal_digest':proposal['digest']})
    contract.pop('contract_digest')
    contract = normalize_task_contract(contract)
    requested_test_bindings(contract, augmented)
    result = {'status':'baseline_verified' if matched and stable else 'not_verified',
        'proposal_digest':proposal['digest'],'project':str(output),'task_contract':contract,
        'source_unchanged':stable,'probes':probes,'source_apply':False,
        'semantic_adequacy':'not_independently_verified',
        'requirement_origin':proposal['task_contract']['origin'],'additional_test_origin':'model_proposal'}
    (work_dir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def _assertion_failure(probe, nodeid):
    reports = [r for r in probe.get('test_reports') or [] if r['nodeid'] == nodeid and r['when'] == 'call']
    return len(reports) == 1 and reports[0].get('failure_message', '').startswith(('assert ', 'AssertionError'))
