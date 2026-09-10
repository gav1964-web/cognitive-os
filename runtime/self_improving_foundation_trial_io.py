"""File output helpers for self-improving foundation trial runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_improvement"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_improving_foundation_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_checkpoint(
    root: Path, baseline: dict[str, Any], training: list[dict[str, Any]], target_score: float
) -> Path:
    payload = {
        "artifact_type": "SelfImprovingFoundationCheckpoint",
        "status": "verification_pending",
        "target_score": target_score,
        "baseline_report_path": baseline.get("report_path"),
        "training": [{
            "project": row.get("project"), "status": row.get("status"),
            "report_path": row.get("report_path"), "outcome": row.get("outcome"),
        } for row in training],
    }
    path = root / "artifacts" / "self_improvement" / "self_improving_foundation_checkpoint.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
