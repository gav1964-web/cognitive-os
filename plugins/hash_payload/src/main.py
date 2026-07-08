"""Hash a JSON-serializable payload."""

from __future__ import annotations

import hashlib
import json


def run(payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload["value"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {"hash": "sha256:" + hashlib.sha256(data).hexdigest()}

