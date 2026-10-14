"""Evidence serialization helpers for local historical defect mining."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from cognitive_replay.evidence import (
    HistoricalEvidencePathError, inside, is_relative_to, canonical, file_digest,
    evidence_digest,
)


def write_manifests(
    root: Path, public: dict[str, Any], oracle: dict[str, Any],
) -> dict[str, str]:
    directory = root / "artifacts" / "self_development" / "historical_defect_mining"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    paths = {
        "public": directory / f"public_manifest_{stamp}.json",
        "oracle": directory / f"sealed_oracle_{stamp}.json",
    }
    for name, payload in (("public", public), ("oracle", oracle)):
        paths[name].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {name: path.relative_to(root).as_posix() for name, path in paths.items()}
