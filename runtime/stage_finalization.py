"""End-of-stage size gate, bounded LLM planning and verified source extraction."""
from __future__ import annotations

import difflib
import json
import uuid
from pathlib import Path

from .repo_lint import _python_source_paths, lint_repository, size_warnings
from .source_refactor_analysis import analyze_module, digest


def audit_stage(root: Path, *, phase: str = 'final', max_lines: int = 400) -> dict:
    if phase not in {'development', 'final'} or max_lines < 10:
        raise ValueError('invalid_phase_or_line_limit')
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('project_root_does_not_exist')
    violations = [v.to_dict() for v in lint_repository(root, max_python_lines=max_lines)]
    tasks = [analyze_module(root, v['path'], max_lines=max_lines) for v in violations[:8]]
    return {'schema_version': 'stage_finalization.v1', 'scope': 'source_size_finalization', 'phase': phase,
            'status': 'needs_refactoring' if violations else 'completed',
            'stage_complete': not violations, 'blocking': bool(violations) and phase == 'final',
            'root': str(root), 'max_python_lines': max_lines,
            'checked_files': len(_python_source_paths(root)), 'violations': violations,
            'warnings': [v.to_dict() for v in size_warnings(root, warning_lines=min(350, max_lines),
                                                         max_python_lines=max_lines)],
            'tasks': tasks, 'tasks_truncated': len(violations) > len(tasks), 'source_applied': False}


def finalize_stage(root: Path, *, repair: bool = False, apply: bool = False,
                   phase: str = 'final', max_lines: int = 400, test_targets: list[str] | None = None,
                   pytest_plugins: list[str] | None = None, timeout: int = 180,
                   work_root: Path | None = None, planner=None) -> dict:
    root = root.resolve()
    if apply and not repair:
        raise ValueError('apply_requires_repair')
    if repair and phase != 'final':
        raise ValueError('repair_requires_final_phase')
    report = audit_stage(root, phase=phase, max_lines=max_lines)
    if not repair or report['stage_complete']:
        return _public(report)
    if not test_targets:
        return _stopped(report, 'explicit_regression_scope_required')
    if report['tasks_truncated'] or len(report['tasks']) > 3:
        return _stopped(report, 'split_stage_into_at_most_three_oversized_modules')
    if any(not task['candidates'] for task in report['tasks']):
        return _stopped(report, 'unsupported_module_requires_design')
    from .source_refactor_patch import build_extraction, navigation_edit
    from .source_refactor_planner import propose_extraction
    from .stage_finalization_workspace import inventory, snapshot, write_edits, changed_files, apply_verified
    from .stage_finalization_verification import verify_snapshot
    work_root = (work_root or root / 'artifacts/stage_finalization').resolve()
    if work_root == root or root.is_relative_to(work_root):
        raise ValueError('work_directory_must_not_contain_source_root')
    if work_root.is_relative_to(root):
        from .repo_lint import _is_excluded
        if not _is_excluded(root, work_root):
            raise ValueError('in_project_work_directory_must_be_an_excluded_artifact_directory')
    work = work_root / ('stage-' + uuid.uuid4().hex[:10])
    work.mkdir(parents=True, exist_ok=False)
    report.update(work_directory=str(work), plans=[], telemetry=[])
    try:
        before = inventory(root)
        report['source_digest'] = digest(json.dumps(before, sort_keys=True).encode())
        baseline, sandbox = work / 'baseline', work / 'sandbox'
        snapshot(root, baseline, before)
        report['baseline'] = verify_snapshot(baseline, work / 'baseline_checks', test_targets=test_targets,
                                             timeout=timeout, pytest_plugins=pytest_plugins)
        if changed_files(baseline, before):
            return _stopped(report, 'baseline_tests_changed_source')
        if report['baseline']['status'] != 'passed':
            return _stopped(report, 'baseline_verification_failed')
        edits, moves = {}, {}
        for task in report['tasks']:
            plan, telemetry = (planner or propose_extraction)(task)
            report['telemetry'].extend(telemetry)
            report['plans'].append({'path': task['path'], 'plan': plan})
            patch = build_extraction(root, task, plan)
            if edits.keys() & patch.keys():
                raise ValueError('cross_task_destination_collision')
            edits.update(patch)
            moves[task['path']] = [p for p in patch if p != task['path']]
        edits.update(navigation_edit(root, moves))
        snapshot(root, sandbox, before)
        write_edits(sandbox, edits)
        expected = {**before, **{name: digest(data) for name, data in edits.items()}}
        report['patch_files'] = sorted(edits)
        (work / 'patch.diff').write_text(_diff(root, edits), encoding='utf-8')
        report['sandbox_audit'] = _public(audit_stage(sandbox, max_lines=max_lines))
        if not report['sandbox_audit']['stage_complete']:
            return _stopped(report, 'sandbox_line_limit_failed')
        report['verification'] = verify_snapshot(sandbox, work / 'patch_checks', test_targets=test_targets,
                                                 timeout=timeout, pytest_plugins=pytest_plugins)
        report['checks'] = {
            'regression_passed': report['verification']['status'] == 'passed',
            'test_collection_unchanged': report['verification'].get('collected') == report['baseline'].get('collected'),
            'passing_count_preserved': report['verification'].get('passing') == report['baseline'].get('passing'),
            'sandbox_source_unchanged_by_tests': not changed_files(sandbox, expected),
            'original_source_unchanged': not changed_files(root, before),
        }
        if not all(report['checks'].values()):
            return _stopped(report, 'verification_or_source_invariant_failed')
        report.update(status='verified_patch', stage_complete=False, blocking=True,
                      patch=str(work / 'patch.diff'), sandbox=str(sandbox),
                      verification_scope='exact_function_moves_and_selected_regression_tests')
        if apply:
            apply_verified(root, before, edits)
            report.update(status='completed', stage_complete=True, blocking=False, source_applied=True)
    except Exception as exc:
        # Provider errors may contain request text or credentials; never persist raw HTTP bodies.
        from .local_inference import LocalInferenceError
        if isinstance(exc, LocalInferenceError):
            report['telemetry'].extend(getattr(exc, 'finalization_telemetry', []))
            report['llm_failure_kind'] = getattr(exc, 'finalization_failure_kind', 'unclassified')
            report = _stopped(report, 'llm_unavailable_or_invalid_response')
        elif isinstance(exc, (ValueError, SyntaxError)):
            report = _stopped(report, 'plan_or_source_rejected:' + str(exc)[:160])
        else:
            report = _stopped(report, 'finalization_error:' + type(exc).__name__)
    report = _public(report)
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def _stopped(report: dict, reason: str) -> dict:
    result = _public({**report, 'status': 'needs_replanning', 'reason': reason,
                      'stage_complete': False, 'blocking': True})
    if report.get('work_directory'):
        (Path(report['work_directory']) / 'report.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _public(report: dict) -> dict:
    result = dict(report)
    result['tasks'] = [{**task, 'candidates': [{k: v for k, v in c.items() if k != 'source'}
                                             for c in task['candidates']]} for task in report.get('tasks', [])]
    return result


def _diff(root: Path, edits: dict[str, bytes]) -> str:
    chunks = []
    for name, data in edits.items():
        path = root / name
        old = path.read_text(encoding='utf-8').splitlines(keepends=True) if path.exists() else []
        new = data.decode('utf-8').splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(old, new, fromfile='a/' + name if path.exists() else '/dev/null', tofile='b/' + name))
    return ''.join(chunks)
