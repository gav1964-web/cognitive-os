"""Recover exactly duplicated read-only tool requests, never role decisions."""
import json


def duplicated_read(content):
    if not isinstance(content, str) or len(content) > 12000:
        return None
    decoder = json.JSONDecoder()
    try:
        first, end = decoder.raw_decode(content.lstrip())
        rest = content.lstrip()[end:].lstrip()
        second, end = decoder.raw_decode(rest)
    except (ValueError, TypeError):
        return None
    if (rest[end:].strip() or first != second or not isinstance(first, dict)
            or set(first) != {'status', 'reads'} or first['status'] != 'read'
            or not isinstance(first['reads'], list) or not 1 <= len(first['reads']) <= 12):
        return None
    return first


def recover_read(attempt):
    if attempt.get('status') != 'failed':
        return None
    evidence = attempt.get('response_evidence', [])
    if len(evidence) != 1:
        return None
    return duplicated_read(evidence[0].get('content'))
