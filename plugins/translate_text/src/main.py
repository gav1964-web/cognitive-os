"""Deterministic MVP text translation."""

from __future__ import annotations


def run(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload["text"])
    language = _normalize_language(str(payload["target_language"]))
    if language != "German":
        raise ValueError(f"unsupported target language: {payload['target_language']}")
    return {"text": _translate_to_german(text), "language": language}


def _normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"german", "de", "deutsch", "немецкий"}:
        return "German"
    return value.strip()


def _translate_to_german(text: str) -> str:
    dictionary = {
        "hello": "hallo",
        "world": "welt",
        "good morning": "guten morgen",
        "good night": "gute nacht",
        "thank you": "danke",
        "yes": "ja",
        "no": "nein",
    }
    normalized = " ".join(text.strip().lower().split())
    return dictionary.get(normalized, text)
