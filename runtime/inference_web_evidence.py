"""Validate bounded web_evidence.v1 metadata separately from model claims."""
import hashlib
import ipaddress
import re
from urllib.parse import urlsplit


def checked_web_evidence(value, response_text=None):
    if not isinstance(value, dict) or value.get('schema_version') != 'web_evidence.v1':
        return None
    status = value.get('capture_status')
    if status not in {'captured', 'unavailable'}:
        return None
    result = {'schema_version': 'web_evidence.v1', 'capture_status': status,
              'search_usage': 'unknown', 'sources': []}
    if status == 'unavailable':
        return result
    digest = value.get('response_sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        return None
    if response_text is not None and hashlib.sha256(response_text.encode('utf-8')).hexdigest() != digest:
        return None
    result['response_sha256'] = digest
    clip = value.get('clipboard_sha256')
    if isinstance(clip, str) and re.fullmatch(r'[0-9a-f]{64}', clip):
        result['clipboard_sha256'] = clip
    rows = value.get('sources')
    if not isinstance(rows, list) or len(rows) > 8:
        return None
    for row in rows:
        if not isinstance(row, dict) or row.get('origin') not in {'response_link', 'source_panel', 'response_text'}:
            return None
        url = row.get('url')
        if not public_https_url(url):
            continue
        title = row.get('title', '')
        if not isinstance(title, str):
            return None
        result['sources'].append({'url': url, 'title': ' '.join(title.split())[:300],
                                  'origin': row['origin']})
    return result


def public_https_url(url):
    if not isinstance(url, str) or not 1 <= len(url) <= 2048 or any(ord(c) <= 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
                or not host or host.endswith('.') or host in {'localhost', 'localhost.localdomain'}):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return '.' in host and not host.endswith(('.localhost', '.local', '.internal'))
    except ValueError:
        return False
