"""Compare the complete regression selection and eligibility on source copies."""
import ast
import json
import sys
import uuid
from pathlib import Path

from .native_failure_acceptance import _probe
from .source_doctest_contract import preserves_doctests
from .stage_finalization_workspace import inventory, snapshot
from .narrow_type_evidence_binding import content_digest

REQUIRED_CHECKS = ('baseline_completed', 'candidate_completed', 'original_tests_retained',
    'no_new_skips', 'no_duplicate_selection', 'source_copies_unchanged', 'input_projects_unchanged')


def regression_scope_is_verified(report):
    return bool(isinstance(report, dict) and report.get('schema_version')=='native_regression_scope.v1'
        and report.get('status')=='passed'
        and all((report.get('checks') or {}).get(k) is True for k in REQUIRED_CHECKS)
        and all((report.get('checks') or {}).values())
        and report.get('baseline_inventory_digest') and report.get('candidate_inventory_digest')
        and report.get('digest')==content_digest({k:v for k,v in report.items() if k!='digest'}))


def verify_regression_scope(*, root, baseline, candidate, intake):
    root, baseline, candidate = (Path(p).resolve() for p in (root, baseline, candidate))
    work = root/'artifacts/native_regression_scope'/('scope-'+uuid.uuid4().hex[:10])
    if any(work.is_relative_to(p) or p.is_relative_to(work) for p in (baseline, candidate)):
        raise ValueError('regression_scope_output_must_be_outside_projects')
    work.mkdir(parents=True)
    before, patched = inventory(baseline), inventory(candidate)
    report = {'schema_version':'native_regression_scope.v1', 'status':'blocked',
        'baseline_inventory_digest':content_digest(before),'candidate_inventory_digest':content_digest(patched),
        'source_apply':False,'probes':[],'checks':{}}
    try:
        for name in before.keys() | patched.keys():
            if name.endswith('.py') and before.get(name) != patched.get(name):
                original = ast.parse((baseline/name).read_text(encoding='utf-8-sig')) if name in before else ast.Module(body=[],type_ignores=[])
                proposed = ast.parse((candidate/name).read_text(encoding='utf-8-sig')) if name in patched else ast.Module(body=[],type_ignores=[])
                if not preserves_doctests(original, proposed):
                    raise ValueError('regression_doctest_contract_changed')
        args = [*intake.get('pytest_arguments',[]), '--maxfail=0']
        plugins = list(intake.get('nested_pytest_plugins') or [])
        python = Path(intake.get('interpreter_path') or sys.executable)
        nodes = list(intake.get('regression_targets') or ['.'])
        for name, source, expected in (('baseline',baseline,before),('candidate',candidate,patched)):
            copy=work/name
            snapshot(source,copy,expected)
            probe=_probe(copy,work/(name+'-check'),nodes,plugins,
                int(intake.get('timeout_seconds') or 120),python,collect_nodeids=True,pytest_arguments=args)
            probe['source_copy_unchanged']=inventory(copy)==expected
            report['probes'].append(probe)
        control, changed = report['probes']
        original_nodes, candidate_nodes = control['selected_nodeids'] or [], changed['selected_nodeids'] or []
        def skipped(probe):
            return {r['nodeid'] for r in probe['test_reports'] or [] if r['outcome']=='skipped'}
        def completed(probe):
            return {r['nodeid'] for r in probe['test_reports'] or [] if r['when']=='teardown'}
        report['checks']={
            'baseline_completed':control['returncode'] in (0,1) and bool(original_nodes)
                and completed(control)==set(original_nodes),
            'candidate_completed':changed['returncode']==0 and completed(changed)==set(candidate_nodes),
            'original_tests_retained':bool(original_nodes) and set(original_nodes)<=set(candidate_nodes),
            'no_new_skips':not ((skipped(changed)-skipped(control)) & set(original_nodes)),
            'no_duplicate_selection':len(original_nodes)==len(set(original_nodes)) and len(candidate_nodes)==len(set(candidate_nodes)),
            'source_copies_unchanged':all(p['source_copy_unchanged'] for p in report['probes']),
            'input_projects_unchanged':inventory(baseline)==before and inventory(candidate)==patched}
        report['status']='passed' if all(report['checks'].values()) else 'failed'
        report['removed_nodeids']=sorted(set(original_nodes)-set(candidate_nodes))
        report['newly_skipped_nodeids']=sorted((skipped(changed)-skipped(control)) & set(original_nodes))
    except (ValueError,OSError,TypeError,KeyError,SyntaxError) as exc:
        report['reason']=str(exc)
    report['receipt_path']=str(work/'scope.json')
    report['digest']=content_digest(report)
    Path(report['receipt_path']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
