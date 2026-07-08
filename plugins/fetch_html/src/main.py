"""Deterministic mock HTML fetcher for the MVP."""

from __future__ import annotations

_TRANSIENT_ONCE_SEEN = False


def run(payload: dict[str, object]) -> dict[str, object]:
    global _TRANSIENT_ONCE_SEEN
    url = str(payload["url"])
    if url == "mock://ok":
        return {"html": "<html><head><title>Cognitive OS MVP</title></head><body>ok</body></html>"}
    if url == "mock://transient_once":
        if not _TRANSIENT_ONCE_SEEN:
            _TRANSIENT_ONCE_SEEN = True
            raise TimeoutError("simulated transient timeout")
        return {"html": "<html><head><title>Recovered After Retry</title></head><body>ok</body></html>"}
    if url == "mock://broken_dependency":
        return {"html": "<html><head><title>__SIMULATE_IMPORT_ERROR__</title></head></html>"}
    if url.startswith("mock://"):
        raise ValueError(f"unknown mock url: {url}")
    raise TimeoutError("real network fetching is disabled in MVP")
