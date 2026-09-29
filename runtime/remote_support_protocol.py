"""Transport-independent authenticated support envelopes and a file mailbox.

HMAC authenticates a pre-provisioned peer; it does not encrypt attachments.
Keys and local policy must never be placed in the mailbox.
"""
import hashlib
import hmac
import json
import os
import re
import uuid
from pathlib import Path

SCHEMA = 'cos.remote_support.v1'
MAX_BYTES = 2_000_000
KINDS = {'incident', 'context_request', 'context', 'patch', 'result'}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError('support_invalid_id')
    return value


def relative_path(name):
    if not isinstance(name, str) or len(name) > 240:
        raise ValueError('support_invalid_path')
    parts = name.split('/')
    reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(10)),
                *(f'lpt{i}' for i in range(10))}
    if any(not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', p)
           or p.endswith(('.', ' ')) or p.split('.')[0].lower() in reserved for p in parts):
        raise ValueError('support_invalid_path')
    return name


def owned(root, name):
    root = Path(root).resolve()
    path = root / relative_path(name)
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('support_link_not_allowed')
    if not path.resolve().is_relative_to(root):
        raise ValueError('support_path_escape')
    return path


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('support_duplicate_json_key')
        result[key] = value
    return result


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('support_message_too_large')
    return json.loads(raw, object_pairs_hook=_unique)


def envelope(kind, incident, payload, key, *, sender, reply_to=None):
    body = {'schema': SCHEMA, 'id': uuid.uuid4().hex, 'incident': incident,
            'kind': kind, 'sender': sender, 'reply_to': reply_to, 'payload': payload}
    body['mac'] = hmac.new(key, encoded(body), hashlib.sha256).hexdigest()
    verify(body, key, sender=sender)
    return body


def verify(message, key, *, sender):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError('support_key_too_short')
    fields = {'schema', 'id', 'incident', 'kind', 'sender', 'reply_to', 'payload', 'mac'}
    if not isinstance(message, dict) or set(message) != fields:
        raise ValueError('support_invalid_envelope')
    if len(encoded(message)) > MAX_BYTES:
        raise ValueError('support_message_too_large')
    if (message['schema'] != SCHEMA or message['kind'] not in KINDS
            or message['sender'] != sender or not isinstance(message['payload'], dict)):
        raise ValueError('support_invalid_envelope')
    identifier(message['id'])
    identifier(message['incident'])
    if message['reply_to'] is not None:
        identifier(message['reply_to'])
    body = {k: v for k, v in message.items() if k != 'mac'}
    expected = hmac.new(key, encoded(body), hashlib.sha256).hexdigest()
    if not isinstance(message['mac'], str) or not hmac.compare_digest(expected, message['mac']):
        raise ValueError('support_authentication_failed')
    return message


def publish(mailbox, message):
    path = owned(mailbox, identifier(message['id']) + '.json')
    if path.exists():
        if load(path) != message:
            raise ValueError('support_message_id_collision')
    else:
        save(path, message)
    return path
