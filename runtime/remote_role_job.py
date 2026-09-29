"""Local, immutable binding of a qualified role checkpoint to remote support.

This binds goal/source/test evidence, not permission to trust arbitrary historical
role scores. The worker still reruns native acceptance after a COS update.
"""
from pathlib import Path

from .remote_support_protocol import digest, load, save


def file_hashes(root):
    root = Path(root).resolve()
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in sorted(root.glob('*.json')) if p.is_file() and not p.is_symlink()}


def ledger_usage(path):
    value = load(path)
    known, unknown = 0, 0
    for row in value['jobs'].values():
        if row['state'] == 'done' and type(row.get('reported_tokens')) is int:
            known += row['reported_tokens']
        elif row['state'] in ('started', 'unknown'):
            unknown += row['reserved_tokens']
    return {'reported': known, 'unknown_reserved': unknown}


def auxiliary_hashes(checkpoint):
    path = Path(checkpoint).parent / 'transcript.json'
    return {str(path.resolve()): digest(path.read_bytes()) if path.is_file() else None}


def bind_job(*, project, checkpoint, ledger, goal, python, model, state_dir,
             budget_limit, acceptance, bootstrap_root, max_calls=24, max_input_bytes=65000,
             known_calls=()):
    from .feature_workspace import inventory
    project, checkpoint = Path(project).resolve(), Path(checkpoint).resolve()
    report = load(checkpoint / 'report.json')
    expected = inventory(project)
    if (report['status'] != 'spec_qualified' or report['goal'] != goal
            or Path(report['project']).resolve() != project or report.get('attempts')
            or load(checkpoint / 'source-inventory.json') != expected):
        raise ValueError('remote_role_requires_current_qualified_spec')
    from .feature_checkpoint import load_roles, qualified_spec
    load_roles(checkpoint, project, expected, goal)
    spec = qualified_spec(checkpoint)
    if not spec or not report.get('frozen_test_hashes'):
        raise ValueError('remote_role_requires_frozen_acceptance')
    if not 1 <= budget_limit < 1000000 or not 1 <= max_calls <= 40:
        raise ValueError('remote_role_bounded_series_required')
    if ledger_usage(ledger)['unknown_reserved']:
        raise ValueError('remote_role_prior_usage_unknown')
    return {'schema': 'remote_role_job.v1', 'project': str(project), 'goal': goal,
        'project_hashes': expected, 'checkpoint': str(checkpoint),
        'checkpoint_hashes': file_hashes(checkpoint), 'frozen_tests': report['frozen_test_hashes'],
        'checkpoint_auxiliary': auxiliary_hashes(checkpoint),
        'roles': {r: digest(report['artifacts'][r]) for r in ('analyzer', 'architect', 'spec_writer')},
        'python': str(Path(python).resolve()), 'model': model, 'state_dir': str(Path(state_dir).resolve()),
        'budget_limit': budget_limit, 'max_calls': max_calls, 'max_input_bytes': max_input_bytes,
        'initial_ledger': str(Path(ledger).resolve()), 'initial_ledger_sha256': digest(Path(ledger).read_bytes()),
        'known_calls': {str(Path(p).resolve()): digest(Path(p).read_bytes()) for p in known_calls},
        'acceptance': {'argv': acceptance['argv'],
            'files': {str(Path(p).resolve()): digest(Path(p).read_bytes()) for p in acceptance['files']}},
        'bootstrap_root': str(Path(bootstrap_root).resolve())}


def verify_job(context):
    from .feature_workspace import inventory
    binding = context['checkpoint']
    job = load(binding['job_file'])
    if digest(job) != binding['job_sha256'] or job.get('schema') != 'remote_role_job.v1':
        raise ValueError('remote_role_job_changed')
    if (context['task'] != job['goal'] or digest(context['task']) != context['task_digest']
            or digest(binding) != context['checkpoint_digest']):
        raise ValueError('remote_role_task_changed')
    if inventory(Path(job['project'])) != job['project_hashes']:
        raise ValueError('remote_role_target_changed')
    if file_hashes(job['checkpoint']) != job['checkpoint_hashes']:
        raise ValueError('remote_role_checkpoint_changed')
    if auxiliary_hashes(job['checkpoint']) != job['checkpoint_auxiliary']:
        raise ValueError('remote_role_checkpoint_auxiliary_changed')
    if digest(Path(job['initial_ledger']).read_bytes()) != job['initial_ledger_sha256']:
        raise ValueError('remote_role_initial_ledger_changed')
    load_known_calls(job)
    for name, wanted in job['acceptance']['files'].items():
        if digest(Path(name).read_bytes()) != wanted:
            raise ValueError('remote_role_external_acceptance_changed')
    return job


def load_known_calls(job):
    """Pinned accounting evidence only; never replay it as a role decision."""
    from .narrow_type_evidence_binding import content_digest
    rows = []
    for name, expected in job.get('known_calls', {}).items():
        path = Path(name)
        if digest(path.read_bytes()) != expected:
            raise ValueError('remote_role_known_calls_changed')
        calls = load(path)
        if (not isinstance(calls, list) or any(not isinstance(row, dict)
                or row.get('request_digest') != content_digest(row.get('messages')) for row in calls)):
            raise ValueError('remote_role_known_calls_invalid')
        rows.extend(calls)
    return rows


def continuation_ledger(job):
    state = Path(job['state_dir'])
    pointer = state / 'ledger-pointer.json'
    if not pointer.exists():
        return Path(job['initial_ledger'])
    record = load(pointer)
    if record['job_digest'] != digest(job):
        raise ValueError('remote_role_series_identity_changed')
    path = Path(record['path']).resolve()
    if not path.is_relative_to(state.resolve()) or not path.is_file():
        raise ValueError('remote_role_ledger_pointer_invalid')
    return path


def save_ledger_pointer(job, path):
    save(Path(job['state_dir']) / 'ledger-pointer.json',
         {'job_digest': digest(job), 'path': str(Path(path).resolve())})
