"""Finite Boolean model of a deliberately narrow normal-return suffix."""
from itertools import product


def check_model(steps, *, max_predicates=6):
    predicates = list(dict.fromkeys(s['predicate'] for s in steps if s['kind'] == 'observe'))
    if not 1 <= len(predicates) <= max_predicates:
        raise ValueError('return_flag_predicate_limit')
    traces = []
    for values in product((False, True), repeat=len(predicates)):
        inputs = dict(zip(predicates, values))
        flags, events, outcome = {}, [], 'returned'
        for step in steps:
            if step['kind'] == 'observe':
                flags[step['field']] = inputs[step['predicate']]
                events.append({'operation': 'assign', 'field': step['field'], 'value': flags[step['field']]})
            elif step['kind'] == 'reject':
                rejected = flags[step['field']] == step['when']
                events.append({'operation': 'reject_if', 'field': step['field'], 'triggered': rejected})
                if rejected:
                    outcome = 'raised'
                    break
            else:
                raise ValueError('return_flag_unknown_step')
        traces.append({'predicates': inputs, 'flags': flags, 'events': events, 'outcome': outcome})
    returned = [t for t in traces if t['outcome'] == 'returned']
    fields = list(dict.fromkeys(s['field'] for s in steps if s['kind'] == 'observe'))
    return {'assignments_checked': len(traces), 'normal_returns': len(returned),
            'fields': [{'field': field,
                'false_return_witness': next((t for t in returned if t['flags'].get(field) is False), None),
                'all_normal_returns_true_in_model': bool(returned) and all(t['flags'].get(field) is True for t in returned)}
                for field in fields]}
