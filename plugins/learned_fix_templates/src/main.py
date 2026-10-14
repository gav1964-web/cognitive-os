"""Read-only competency contract; proposals never write sources."""
from __future__ import annotations

from .knowledge import load_document
from .task_change import task_change


def run(payload: dict) -> dict:
    operation = payload['operation']
    if operation == 'rules':
        document = load_document()
        return {'status': 'ok', 'rules': {rule: {k: v for k, v in row.items() if k != 'templates'}
                                          | {'templates': [{k: t[k] for k in ('support', 'projects', 'before_text', 'after_text')}
                                                           for t in row['templates']]}
                                          for rule, row in document['rules'].items()}}
    if operation == 'task_change':
        return task_change(payload['goal'], payload['sources'], payload['diagnostics'])
    raise ValueError('unsupported_learned_fix_templates_operation')
