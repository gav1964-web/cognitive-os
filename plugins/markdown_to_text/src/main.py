"""Convert simple Markdown to plain text."""

from __future__ import annotations

import re


def run(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload["markdown"])
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>*\- ]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)
    return {"text": " ".join(text.split())}
