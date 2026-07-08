"""Small deterministic JSON transforms."""

from __future__ import annotations


def run(payload: dict[str, object]) -> dict[str, object]:
    mode = str(payload["mode"])
    data = payload["data"]
    if mode == "identity":
        return {"data": data}
    if mode == "keys":
        if not isinstance(data, dict):
            raise ValueError("json_transform keys mode requires object data")
        return {"data": sorted(str(key) for key in data)}
    raise ValueError(f"unsupported json_transform mode: {mode}")
