"""Hash-bound edits of an unaccepted specification; grants no acceptance."""
from copy import deepcopy
from hashlib import sha256
from pathlib import PurePosixPath

from .feature_quality_draft import draft_binding
from .feature_test_references import expand_test_references
from .narrow_type_evidence_binding import content_digest


CONTRACT = 'unaccepted_spec_delta.v1'
BASES = ('quality_contract_feedback.rejected', 'feedback.rejected_spec')
INSTRUCTION = '''
When specification_delta_base is present, prefer a point correction instead of
regenerating the entire draft. Return {"status":"ready","specification_delta":{
"contract":"unaccepted_spec_delta.v1","base_digest":"<descriptor base_digest>",
"binding_digest":"<descriptor binding_digest>","tests":[
{"op":"add","path":"tests/test_new.py","content":"<complete new test code>"},
{"op":"edit","path":"tests/test_existing.py","before_sha256":"<catalog hash>",
"replacements":[{"old":"<unique exact text>","new":"<replacement text>"}]}],
"set_fields":{"case_plan":["<complete updated rows>"],
"baseline_expectations":["<complete updated rows>"]}}}.
The example rows are placeholders: use the real contract's metadata objects.
Unmentioned files and fields are retained exactly from the named base, not deleted.
No test deletion or changes to accepted tests are permitted through this format.
Each existing file has at most one edit operation, with nonempty unique old text.
Use set_fields only for metadata that needs change; supply complete values for
those fields, preserving earlier coverage. Never put tests/status/reference fields
in set_fields. An ordinary complete specification remains supported.
The expanded complete draft receives fresh audit and native qualification.
'''


def _field(payload, path):
    for key in path.split('.'):
        payload = payload.get(key) if isinstance(payload, dict) else None
    return payload


def _hash(text):
    return sha256(text.encode('utf-8')).hexdigest()


def _tests(spec):
    result = {}
    for test in spec.get('tests', []):
        if (not isinstance(test, dict) or set(test) != {'path', 'content'}
                or not isinstance(test['content'], str)):
            raise ValueError('quality_spec_delta_base_tests')
        path = test['path']
        if (not isinstance(path, str) or not path.startswith('tests/')
                or '\\' in path or ':' in path or '..' in PurePosixPath(path).parts
                or str(PurePosixPath(path)) != path or not path.endswith('.py')
                or path in result):
            raise ValueError('quality_spec_delta_test_path')
        result[path] = test
    if not result:
        raise ValueError('quality_spec_delta_base_tests')
    return result


def descriptor(payload):
    """Reference existing input content without duplicating its potentially large code."""
    for field in BASES:
        base = _field(payload, field)
        if not isinstance(base, dict) or base.get('status') != 'ready':
            continue
        try:
            tests = _tests(base)
        except (ValueError, TypeError):
            continue  # Full-artifact repair is still available for malformed drafts.
        return {'contract': CONTRACT, 'field': field, 'base_digest': content_digest(base),
                'binding_digest': content_digest(draft_binding(payload, 'spec_writer')),
                'tests': [{'path': p, 'content_sha256': _hash(t['content'])}
                          for p, t in tests.items()]}
    return None


def expand(value, payload):
    if 'specification_delta' not in value:
        return value
    if 'test_reference_contract' in payload:
        payload = expand_test_references(payload)
    desc = descriptor(payload)
    delta = value.get('specification_delta')
    if (not desc or payload.get('specification_delta_base') != desc
            or set(value) != {'status', 'specification_delta'} or value['status'] != 'ready'
            or not isinstance(delta, dict) or set(delta) != {
                'contract', 'base_digest', 'binding_digest', 'tests', 'set_fields'}
            or any(delta[k] != desc[k] for k in ('contract', 'base_digest', 'binding_digest'))):
        raise ValueError('quality_spec_delta_identity')
    result = deepcopy(_field(payload, desc['field']))
    tests = _tests(result)
    updates, operations = delta['set_fields'], delta['tests']
    protected = {'tests', 'status', 'immutable_test_refs', 'specification_delta',
                 'test_reference_contract', 'specification_delta_base'}
    if (not isinstance(updates, dict) or protected.intersection(updates)
            or not isinstance(operations, list) or len(operations) > 64):
        raise ValueError('quality_spec_delta_shape')
    frozen = {r['path'] for r in payload.get('immutable_previous_tests', [])}
    touched = set()
    for op in operations:
        if not isinstance(op, dict) or not isinstance(op.get('path'), str):
            raise ValueError('quality_spec_delta_operation')
        path = op['path']
        if path in touched or path in frozen:
            raise ValueError('quality_spec_delta_duplicate_or_frozen')
        touched.add(path)
        if op.get('op') == 'add' and set(op) == {'op', 'path', 'content'} and path not in tests:
            row = {'path': path, 'content': op['content']}
            _tests({'tests': [row]})
            tests[path] = row
            result['tests'].append(row)
        elif (op.get('op') == 'edit' and set(op) == {'op', 'path', 'before_sha256', 'replacements'}
              and path in tests and op['before_sha256'] == _hash(tests[path]['content'])):
            text = tests[path]['content']
            replacements = op['replacements']
            if not isinstance(replacements, list) or not replacements:
                raise ValueError('quality_spec_delta_replacements')
            for replacement in replacements:
                if (not isinstance(replacement, dict) or set(replacement) != {'old', 'new'}
                        or not all(isinstance(v, str) for v in replacement.values())
                        or not replacement['old'] or text.count(replacement['old']) != 1
                        or replacement['old'] == replacement['new']):
                    raise ValueError('quality_spec_delta_replacement_not_unique')
                text = text.replace(replacement['old'], replacement['new'], 1)
            tests[path]['content'] = text
        else:
            raise ValueError('quality_spec_delta_operation_or_hash')
    result.update(deepcopy(updates))
    return result
