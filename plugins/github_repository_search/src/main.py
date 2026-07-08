"""Search public GitHub repositories for external evidence."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.github.com/search/repositories"


def run(payload: dict[str, object]) -> dict[str, object]:
    query = str(payload["query"]).strip()
    limit = max(1, min(int(payload.get("limit", 5)), 10))
    if not query:
        raise ValueError("github_repository_search query must be non-empty")
    data = _request(query, limit)
    repositories = [_repo(row) for row in data.get("items", [])[:limit]]
    return {
        "query": query,
        "source": "github_repository_search",
        "repositories": repositories,
        "total_count": int(data.get("total_count", 0) or 0),
        "incomplete_results": bool(data.get("incomplete_results", False)),
    }


def _request(query: str, limit: int) -> dict[str, object]:
    url = f"{API_URL}?{urlencode({'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': str(limit)})}"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "cognitive-os-knowledge-probe"})
    with urlopen(request, timeout=10) as response:  # nosec: GitHub API allowlist URL
        return json.loads(response.read().decode("utf-8"))


def _repo(row: dict[str, object]) -> dict[str, object]:
    owner = dict(row.get("owner", {}))
    license_info = row.get("license")
    license_key = dict(license_info).get("key") if isinstance(license_info, dict) else None
    return {
        "full_name": row.get("full_name"),
        "html_url": row.get("html_url"),
        "description": row.get("description"),
        "language": row.get("language"),
        "stars": int(row.get("stargazers_count", 0) or 0),
        "owner": owner.get("login"),
        "license": license_key,
    }
