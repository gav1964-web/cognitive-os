from io import BytesIO
from unittest.mock import patch

from plugins.github_repository_search.src.main import run


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return (
            b'{"total_count":1,"incomplete_results":false,"items":[{"full_name":"owner/repo",'
            b'"html_url":"https://github.com/owner/repo","description":"example",'
            b'"language":"Python","stargazers_count":42,"owner":{"login":"owner"},'
            b'"license":{"key":"mit"}}]}'
        )


def test_github_repository_search_contract():
    with patch("plugins.github_repository_search.src.main.urlopen", return_value=_Response()):
        result = run({"query": "python xlsx csv conversion", "limit": 1})

    assert result["source"] == "github_repository_search"
    assert result["repositories"][0]["full_name"] == "owner/repo"
    assert result["repositories"][0]["stars"] == 42
