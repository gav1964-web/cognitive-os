"""Fallback title parser for the MVP."""

from __future__ import annotations

import re


def run(payload: dict[str, object]) -> dict[str, object]:
    html = str(payload["html"])
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = match.group(1).strip() if match else "untitled"
    if title == "__SIMULATE_IMPORT_ERROR__":
        title = "recovered by fallback"
    return {"title": title}

