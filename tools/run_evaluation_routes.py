"""Run task15 adapters; persist honest drafts when v2 evidence is incomplete."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--task', default='task15_uppercase_cli', choices=['task15_uppercase_cli'])
    parser.add_argument('--route', choices=['direct_agent', 'short_chain', 'full_chain'])
    parser.add_argument('--run-dir')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--model-route', choices=['failover', 'primary', 'backup'], default='failover')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.worker:
        return worker(root, Path(args.run_dir).resolve(), args.route, args.task, args.model_route)
    from runtime.evaluation_input_readiness import input_readiness
    from runtime.stage_finalization_workspace import inventory, changed_files
    manifest = json.loads((root / 'evaluation/protocol_v2_manifest.json').read_text(encoding='utf-8'))
    readiness = input_readiness(root, manifest)
    if readiness['status'] != 'inputs_verified':
        raise ValueError('inputs_not_ready')
    task = next(t for t in manifest['tasks'] if t['task_id'] == args.task)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run = root / 'artifacts/evaluation_v2' / ('routes_' + stamp)
    run.mkdir(parents=True, exist_ok=False)
    before = inventory(root)
    write(run / 'source-inventory.json', before)
    write(run / 'manifest.json', manifest)
    write(run / 'plan.json', {
        'task_id': args.task, 'routes': [args.route] if args.route else ['direct_agent', 'short_chain', 'full_chain'],
        'task_digest': manifest['manifest_digest'],
        'checker_sha256': hashlib.sha256((root / 'evaluation/acceptance/check_uppercase_cli.py').read_bytes()).hexdigest(),
        'limits': {'route_seconds': 900, 'agent_turns': 20, 'completion_tokens_per_call': 3000},
        'model_route': args.model_route,
        'source_inventory_sha256': hashlib.sha256((run / 'source-inventory.json').read_bytes()).hexdigest(),
        'claim': 'engineering route trial; independent judge and financial completeness evaluated separately',
    })
    summary = []
    for route in ([args.route] if args.route else ['direct_agent', 'short_chain', 'full_chain']):
        directory = run / route
        workspace = directory / 'project'
        workspace.mkdir(parents=True)
        shutil.copytree(root / task['input_spec']['path'], directory / 'inputs')
        print('Running ' + route, flush=True)
        with (directory / 'worker.log').open('w', encoding='utf-8') as log:
            try:
                process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', '--root', str(root),
                    '--run-dir', str(run), '--task', args.task, '--route', route, '--model-route', args.model_route],
                    cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=900)
                code = process.returncode
            except subprocess.TimeoutExpired:
                code = 124
        receipt = directory / 'draft.json'
        if receipt.exists():
            row = json.loads(receipt.read_text(encoding='utf-8'))
            summary.append({'route': route, 'status': row['status'],
                            'acceptance': row.get('verification', {}).get('acceptance', {}).get('status'),
                            'v2_errors': row.get('v2_errors'), 'returncode': code})
        else:
            summary.append({'route': route, 'status': 'failed', 'returncode': code, 'reason': 'worker_no_receipt'})
        print(json.dumps(summary[-1]), flush=True)
    result = {'status': 'trial_recorded', 'routes': summary, 'run_dir': str(run),
              'changed_maintained_sources': changed_files(root, before), 'independent_judging': 'not_performed'}
    write(run / 'summary.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if all(r['returncode'] == 0 for r in summary) and not result['changed_maintained_sources'] else 1


def worker(root, run, route, task_id, model_route):
    from runtime.local_inference import LocalInferenceConfig
    from runtime.evaluation_route_execution import MeteredChat, verify_task15
    from runtime.evaluation_route_adapters import execute_route
    from runtime.evaluation_evidence import validate_receipt
    from runtime.three_route_evaluation import _tree_digest
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    task = next(t for t in manifest['tasks'] if t['task_id'] == task_id)
    directory, workspace = run / route, run / route / 'project'
    prompt = task['prompt_text'] + '\n\nConstraints:\n' + '\n'.join(task['constraints'])
    prompt += '\n\nSuccess criteria:\n' + '\n'.join(task['success_criteria'])
    chat = MeteredChat(select_model_config(LocalInferenceConfig.from_l45_env(), model_route))
    checks = []
    def verify(project):
        result = verify_task15(project, directory / 'checks' / str(len(checks) + 1))
        checks.append(result)
        return result
    try:
        execution = execute_route(route, root=root, workspace=workspace, prompt=prompt, chat=chat, verify=verify)
    except Exception as exc:
        execution = {'status': 'failed', 'reason': type(exc).__name__}
    verification = verify(workspace)
    input_changed = _tree_digest(directory / 'inputs') != task['input_spec']['tree_digest']
    write(directory / 'execution.json', execution)
    write(directory / 'llm-trace.json', chat.records)
    write(directory / 'verification.json', verification)
    artifacts = []
    paths = [directory / 'execution.json', directory / 'llm-trace.json', directory / 'verification.json']
    paths += [p for p in workspace.rglob('*') if p.is_file() and 'inputs' not in p.relative_to(workspace).parts
              and not any(part.startswith('.') or part == '__pycache__' for part in p.relative_to(workspace).parts)]
    for path in paths:
        artifacts.append({'path': path.relative_to(root).as_posix(), 'digest': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()})
    usage = chat.usage()
    models = sorted({r['model'] for r in chat.records if r.get('model_reported')})
    receipt = {
        'artifact_type': 'ThreeRouteExecutionReceiptDraft', 'task_id': task_id, 'route': route,
        'manifest_digest': manifest['manifest_digest'], 'prompt_digest': task['prompt_digest'],
        'input_digest': task['input_digest'], 'executor': execution.get('executor', 'native_' + route),
        'status': 'completed' if execution['status'] == 'completed' and verification['status'] == 'passed' and not input_changed else execution['status'] if execution['status'] != 'completed' else 'failed',
        'model': models[0] if len(models) == 1 else None,
        'runtime_seconds': round(time.monotonic() - chat.started, 3),
        'estimated_cost': None, 'token_usage': {'input': usage['input'], 'output': usage['output']},
        'usage_observation': usage, 'llm_attempts': chat.records,
        'llm_trace': (directory / 'llm-trace.json').relative_to(root).as_posix(),
        'manual_corrections': [], 'acceptance_checks': verification['acceptance']['checks'],
        'artifacts': artifacts, 'verification': verification,
        'judge_payload': {'status': execution['status'], 'acceptance': verification['acceptance']},
        'safety': {'source_mutation_detected': input_changed}, 'uses_cognitive_os': route != 'direct_agent',
    }
    policy = json.loads((root / 'config/evaluation_protocol_v2.json').read_text(encoding='utf-8'))
    receipt['v2_errors'] = validate_receipt(receipt, manifest, policy, artifact_root=root)
    write(directory / 'draft.json', receipt)
    return 0


def select_model_config(config, route):
    import dataclasses
    if route == 'failover':
        return config
    if route == 'backup':
        if not config.fallbacks:
            raise ValueError('backup_model_not_configured')
        return dataclasses.replace(config.fallbacks[0], fallbacks=())
    if route == 'primary':
        return dataclasses.replace(config, fallbacks=())
    raise ValueError('unknown_model_route')


if __name__ == '__main__':
    raise SystemExit(main())
