"""Normalize whitespace in text."""

from __future__ import annotations


def run(payload: dict[str, object]) -> dict[str, object]:
    text = " ".join(str(payload["text"]).split())
    return {"text": text}

