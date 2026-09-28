"""Shared content binding and score validation for narrow-lane evidence."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter


def content_digest(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


def valid_score(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10


def index_cells(evaluation: dict) -> tuple[dict, Counter]:
    rows = evaluation.get('cells') or []
    cells, counts = {}, Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = (str(row.get('role_id')), str(row.get('project_stratum')))
        cells[identity] = row
        counts[identity] += 1
    return cells, counts
