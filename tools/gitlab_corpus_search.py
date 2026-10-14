"""Bounded concurrent GitLab search transport for blind corpora."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from urllib.error import HTTPError, URLError

API_URL = "https://gitlab.com/api/v4/projects"


def search_stratum(
    stratum: dict[str, Any], policy: dict[str, Any], *,
    excluded_names: set[str], excluded_repos: set[str], needed: int,
    project_row: Callable[[dict[str, Any]], dict[str, Any]],
    unseen: Callable[[dict[str, Any], set[str], set[str]], bool],
    eligible: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    maximum = int(policy.get("maximum_search_pages") or 2)
    page_start = max(1, int(policy.get("search_page_start") or 1))
    page_stop = page_start + maximum - 1
    batch_size = max(1, int(policy.get("search_page_batch_size") or 1))
    workers = max(1, int(policy.get("search_workers") or 4))
    order_by = str(policy.get("search_order_by") or "star_count")
    for first_page in range(page_start, page_stop + 1, batch_size):
        pages_in_batch = range(first_page, min(page_stop, first_page + batch_size - 1) + 1)
        label = f"{first_page}-{pages_in_batch.stop - 1}" if len(pages_in_batch) > 1 else str(first_page)
        print(f"[{stratum['id']}] search pages {label}/{page_start}-{page_stop}", file=sys.stderr, flush=True)
        requests = [
            _params(query, page, order_by=order_by)
            for page in pages_in_batch
            for query in stratum["queries"]
        ]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pages = list(pool.map(lambda params: search_page(params, policy), requests))
        for items in pages:
            for item in items:
                row = project_row(item)
                by_name.setdefault(row["full_name"].lower(), row)
        rows = [row for row in by_name.values()
                if unseen(row, excluded_names, excluded_repos) and eligible(row, policy)]
        print(f"[{stratum['id']}] eligible unseen: {len(rows)}/{needed}", file=sys.stderr, flush=True)
        if len(rows) >= needed:
            break
    return sorted(by_name.values(), key=lambda row: (-row["stars"], row["full_name"].lower()))


def search_page(params: dict[str, str], policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = policy or {}
    timeout = float(settings.get("api_timeout_seconds") or 45)
    attempts = max(1, int(settings.get("api_retry_attempts") or 2))
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "cognitive-os-gitlab-blind-corpus"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
                return [dict(row) for row in payload if isinstance(row, dict)]
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == attempts - 1:
                if 500 <= exc.code < 600:
                    return []
                raise
            time.sleep(int(exc.headers.get("Retry-After") or (attempt + 1) * 2))
        except (TimeoutError, URLError):
            if attempt == attempts - 1:
                return []
            time.sleep(attempt + 1)
    return []


def _params(query: str, page: int, *, order_by: str = "star_count") -> dict[str, str]:
    return {
        "search": str(query), "simple": "true", "with_programming_language": "Python",
        "archived": "false", "order_by": order_by, "sort": "desc",
        "per_page": "100", "page": str(page),
    }
