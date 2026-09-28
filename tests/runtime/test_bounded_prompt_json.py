from __future__ import annotations

import json

from runtime.bounded_prompt_json import bounded_prompt_json


def test_bounded_prompt_json_remains_valid_when_evidence_is_large():
    text = bounded_prompt_json(
        {
            "target": "pkg/core.py:run",
            "source_context": "x" * 20000,
            "obligations": [{"id": str(index), "given": "y" * 1000} for index in range(20)],
        },
        max_chars=1000,
    )

    payload = json.loads(text)

    assert len(text) <= 1000
    assert payload["target"] == "pkg/core.py:run"
    assert "truncated" in text


def test_bounded_prompt_json_rejects_unusable_limit():
    try:
        bounded_prompt_json({"target": "x"}, max_chars=20)
    except ValueError as exc:
        assert "at least 64" in str(exc)
    else:
        raise AssertionError("expected ValueError")
