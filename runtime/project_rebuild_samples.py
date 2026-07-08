"""Data sampling helpers for rebuild trials."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FALLBACK_SAMPLES: dict[str, Any] = {
    "kursk_vector_map.json": {"type": "FeatureCollection", "features": []},
    "kursk_nodes.json": [{"name": "Sample object", "type": "object", "lat": 51.73, "lon": 36.19, "settlement": "Kursk"}],
    "incidents.json": {"dates": [], "groups": [], "events": [], "stats": {}},
    "branches_atms.json": {"type": "FeatureCollection", "features": []},
}


def build_sample_data_files(spec: dict[str, Any]) -> dict[str, str]:
    source_dir = Path(str(spec.get("source_project") or "."))
    result = {}
    for row in spec.get("data_artifacts", []):
        name = str(row.get("path") or "")
        if not row.get("exists") or name not in FALLBACK_SAMPLES:
            continue
        result[name] = json.dumps(_sample_json(source_dir / name, name), ensure_ascii=False, indent=2) + "\n"
    return result


def _sample_json(path: Path, name: str) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return FALLBACK_SAMPLES[name]
    return _thin(value)


def _thin(value: Any) -> Any:
    if isinstance(value, list):
        return [_thin(item) for item in value[:100]]
    if isinstance(value, dict):
        if value.get("type") == "FeatureCollection" and isinstance(value.get("features"), list):
            return {**value, "features": [_thin(item) for item in value["features"][:100]]}
        result = {}
        for key, item in value.items():
            if isinstance(item, list):
                result[key] = [_thin(row) for row in item[:100]]
            elif isinstance(item, dict):
                result[key] = _thin(item)
            else:
                result[key] = item
        return result
    return value
