"""Extract href values from simple HTML."""

from __future__ import annotations

import re


def run(payload: dict[str, object]) -> dict[str, object]:
    html = str(payload["html"])
    links = re.findall(r"""href=["']([^"']+)["']""", html, flags=re.IGNORECASE)
    return {"links": links}
