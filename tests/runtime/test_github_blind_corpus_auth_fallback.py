from urllib.error import HTTPError
from unittest.mock import patch

from tools.github_blind_corpus import _search_page


def test_search_uses_authenticated_gh_after_urllib_rate_limit(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    error = HTTPError("https://api.github.com", 403, "rate limit", {}, None)

    with (
        patch("tools.github_blind_corpus._search_with_urllib", side_effect=error),
        patch("tools.github_blind_corpus.shutil.which", return_value="gh"),
        patch("tools.github_blind_corpus._search_with_gh", return_value={"items": []}) as fallback,
    ):
        result = _search_page({"q": "topic:test"})

    assert result == {"items": []}
    fallback.assert_called_once_with({"q": "topic:test"})
