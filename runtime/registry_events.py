"""Registry transaction event log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_registry_event(root: Path, event: dict[str, Any]) -> Path:
    log_dir = root / "artifacts" / "registry"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "events.jsonl"
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return log_path

