"""Fetch bounded public HTTPS evidence with checked redirects and pinned DNS."""
import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import unquote, urljoin, urlsplit

from .inference_web_evidence import public_https_url


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.rows.append(data)


def checked_url(url, allowed_domains):
    if not public_https_url(url) or urlsplit(url).hostname not in allowed_domains:
        raise ValueError('research_source_not_allowlisted')
    parts = urlsplit(url)
    decoded = unquote(unquote(parts.path))
    if '\\' in decoded or any(segment in {'.', '..'} for segment in decoded.split('/')):
        raise ValueError('research_source_ambiguous_path')
    return parts


def public_address(host):
    addresses = {row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('research_source_not_public')
    return sorted(addresses)[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        address = public_address(self.host)
        raw = socket.create_connection((address, 443), self.timeout)
        try:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_source(url, allowed_domains):
    original = url
    for attempt in range(4):
        parts = checked_url(url, allowed_domains)
        connection = PinnedHTTPS(parts.hostname, timeout=15)
        try:
            connection.request('GET', (parts.path or '/') + ('?' + parts.query if parts.query else ''),
                               headers={'User-Agent': 'CognitiveOS-Evidence/1', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader('Location')
                if not location:
                    raise ValueError('research_redirect_missing_location')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError('research_source_http_' + str(response.status))
            kind = response.getheader('Content-Type', '').split(';')[0].strip()
            if kind not in {'text/html', 'text/plain', 'application/xhtml+xml'}:
                raise ValueError('research_source_unsupported_content')
            data = response.read(512_001)
            if len(data) > 512_000:
                raise ValueError('research_source_too_large')
        finally:
            connection.close()
        parser = Text()
        parser.feed(data.decode('utf-8', errors='replace'))
        return {'url': original, 'final_url': url, 'sha256': hashlib.sha256(data).hexdigest(),
                'text': ' '.join(' '.join(parser.rows).split())}
    raise ValueError('research_redirect_limit')
