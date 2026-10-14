"""Execute a model-authored diagnostic on copied project data, retaining evidence.

Trusted local project/model code, like native acceptance; not an OS sandbox.
The proposal writes RESULT, a bounded JSON object, and must preserve input bytes.
"""
import ast
import json
import os
import subprocess
from pathlib import Path

from cognitive_replay.bounded_process import _run_bounded_process
from .feature_acceptance import save
from .feature_corpus_checks import input_inventory
from .feature_workspace import copy_source, digest, inventory, owned_path


def run_data_probe(*, project, work, python, proposal, inputs, timeout=120):
    project, work = Path(project).resolve(), Path(work).resolve()
    if (work.exists() or work.is_relative_to(project) or project.is_relative_to(work)
            or not 1 <= timeout <= 300):
        raise ValueError('feature_probe_requires_fresh_copy')
    code = proposal['code']
    if not isinstance(code, str) or len(code.splitlines()) > 200 or len(code.encode()) > 16000:
        raise ValueError('feature_probe_code_limit')
    ast.parse(code)
    expected = inventory(project)
    corpus = input_inventory(project, inputs, expected)
    root = work / 'project'
    work.mkdir(parents=True)
    copy_source(project, root, {**expected, **corpus})
    script = work / 'model_probe.py'; script.write_text(code, encoding='utf-8')
    save(work / 'proposal.json', proposal)
    result = {'schema_version': 'feature_data_probe.v1', 'source_hashes': expected,
        'input_hashes': corpus, 'script_sha256': digest(script.read_bytes()),
        'author': 'COS model', 'source_apply': False, 'status': 'blocked'}
    bootstrap = ('import sys,json,runpy;from pathlib import Path;root=Path(sys.argv[1]);'
                 'sys.path[:0]=[str(root),str(root/"src")];'
                 'ns=runpy.run_path(sys.argv[2],init_globals={"PROJECT":root,"INPUTS":json.loads(sys.argv[3])});'
                 'print(json.dumps(ns["RESULT"],ensure_ascii=True))')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None)
    try:
        ran = _run_bounded_process([str(python), '-I', '-c', bootstrap, str(root),
            str(script), json.dumps(inputs)], cwd=root, env=env, timeout=timeout)
        (work / 'stdout.txt').write_text(ran.stdout, encoding='utf-8')
        (work / 'stderr.txt').write_text(ran.stderr, encoding='utf-8')
        if ran.returncode or len(ran.stdout.encode()) > 64000:
            raise ValueError('feature_probe_failed_or_output_limit')
        result['observations'] = json.loads(ran.stdout)
        if not isinstance(result['observations'], dict):
            raise ValueError('feature_probe_result_not_object')
        result['status'] = 'observed'
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        result['reason'] = str(exc)[-2000:]
    result['source_unchanged'] = inventory(project) == expected and inventory(root) == expected
    result['inputs_unchanged'] = all(
        owned_path(r, n).is_file() and digest(owned_path(r, n).read_bytes()) == h
        for r in (root, project) for n, h in corpus.items())
    if not result['source_unchanged'] or not result['inputs_unchanged']:
        result.update(status='blocked', reason='feature_probe_changed_inputs')
    save(work / 'report.json', result)
    return result
