from unittest.mock import patch

import pytest

from plugins.official_docs_fetch.src.main import run


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return b"<html><head><title>Docs</title></head><body><h1>Install</h1><p>Use pip.</p></body></html>"


def test_official_docs_fetch_contract():
    with patch("plugins.official_docs_fetch.src.main.urlopen", return_value=_Response()):
        result = run({"url": "https://docs.python.org/3/library/csv.html", "max_chars": 200})

    assert result["source"] == "official_docs_fetch"
    assert result["domain"] == "docs.python.org"
    assert result["title"] == "Docs"
    assert "Use pip." in result["text_excerpt"]
    assert result["content_hash"].startswith("sha256:")


def test_official_docs_fetch_blocks_unlisted_domain():
    with pytest.raises(ValueError):
        run({"url": "https://example.com/not-official"})
