"""Inspect a repository and verify a supplied Git fix with the Replay package."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from cognitive_inspect import scan_project_tree, detect_project_stack
from cognitive_replay import freeze_environment_profile, qualify_candidate_in_sandbox
from cognitive_replay.git import _git

from .stage_finalization_workspace import owned_path


def review_project_fix(*, root: Path, project: str, baseline: str, fix: str,
                       tests: list[str], production: list[str], wheels: list[Path], timeout: int = 180) -> dict:
    root = root.resolve()
    source = owned_path(root, project)
    if not tests or not production or set(tests) & set(production):
        raise ValueError('distinct_test_and_production_files_required')
    for revision in (baseline, fix):
        if not re.fullmatch(r'[0-9a-fA-F]{7,40}', revision):
            raise ValueError('use_explicit_commit_hashes')
    for name in [*tests, *production]:
        if name.startswith('-'):
            raise ValueError('invalid_source_path')
        owned_path(source, name)
    before = _git(source, ['status', '--porcelain=v1'])
    if before.strip():
        raise ValueError('source_repository_must_be_clean')
    facts = {'tree': scan_project_tree({'path': str(source)}),
             'stack': detect_project_stack({'path': str(source)})}
    baseline = _git(source, ['rev-parse', baseline + '^{commit}']).strip()
    fix = _git(source, ['rev-parse', fix + '^{commit}']).strip()
    public = {'project_root': project, 'baseline_revision': baseline}
    oracle = {'fix_revision': fix, 'test_files': tests, 'test_entry_files': tests, 'production_files': production}
    for key, names in [('test_patch_sha256', tests), ('production_patch_sha256', production)]:
        patch = _git(source, ['diff', '--no-ext-diff', baseline, fix, '--', *names])
        oracle[key] = 'sha256:' + hashlib.sha256(patch.encode('utf-8')).hexdigest()
    profile = freeze_environment_profile(root=root, wheels=wheels)
    replay = qualify_candidate_in_sandbox(root=root, public=public, oracle=oracle,
                                           environment_profile=profile, timeout=timeout)
    valid = replay['status'] == 'qualified' and all(replay.get(key) for key in (
        'source_head_unchanged', 'source_worktree_unchanged', 'source_worktree_registry_unchanged', 'sandbox_cleaned'))
    return {'schema_version': 'project_fix_review.v1', 'status': 'verified' if valid else 'not_verified',
            'scope': 'supplied_git_fix_and_selected_tests', 'project': project,
            'baseline': baseline, 'fix': fix, 'facts': facts, 'replay': replay,
            'interpretation': 'This verifies a supplied fix; it does not claim the system discovered the repair.'}
