"""Manual promotion transaction for exception pickle reconstruction knowledge."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_promotion_contract import prepare_promotion_catalog as _catalog


CATALOG_PATH = Path("plugins/exception_pickle/knowledge/exception_pickle_reconstruction_patterns.json")


def promote_exception_pickle_reconstruction(
    *,
    root: Path,
    readiness_path: Path,
    evaluator_review_path: Path,
    holdout_path: Path,
    explicit_approval: bool,
    regression_passed: bool,
    config_doctor_passed: bool,
    catalog_path: Path = CATALOG_PATH,
) -> dict[str, Any]:
    """Promote the strict exception pickle pattern only after all gates pass."""
    root = root.resolve()
    readiness = _read_json(root, readiness_path)
    evaluator = _read_json(root, evaluator_review_path)
    holdout = _read_json(root, holdout_path)
    catalog_file = catalog_path if catalog_path.is_absolute() else root / catalog_path
    before = catalog_file.read_bytes() if catalog_file.exists() else b""
    checks = {
        "explicit_approval": explicit_approval,
        "readiness_status": readiness.get("status") == "eligible_for_promotion_review",
        "readiness_allows_review": readiness.get("promotion_review_allowed") is True,
        "readiness_has_autonomous_activation_gate": readiness.get(
            "autonomous_activation_allowed"
        )
        is True,
        "readiness_blocks_direct_kb_promotion": readiness.get("kb_promotion_allowed")
        is False,
        "independent_evaluator_passed": evaluator.get("status") == "passed",
        "holdout_transaction_ready": holdout.get("status") == "holdout_ready",
        "regression_tests": regression_passed,
        "config_doctor": config_doctor_passed,
        "source_apply_forbidden": True,
    }
    status = "promoted" if all(checks.values()) else "blocked"
    report = {
        "artifact_type": "ExceptionPicklePromotionTransaction",
        "schema_version": "exception_pickle_promotion_transaction.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "catalog_path": _relative(root, catalog_path),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "evidence": {
            "readiness": _relative(root, readiness_path),
            "evaluator_review": _relative(root, evaluator_review_path),
            "holdout": _relative(root, holdout_path),
            "supervised_verified_count": dict(readiness.get("evidence") or {}).get(
                "supervised_verified_count"
            ),
            "autonomous_verified_count": dict(readiness.get("evidence") or {}).get(
                "autonomous_verified_count"
            ),
            "holdout_project_count": holdout.get("holdout_project_count"),
            "holdout_candidate_count": holdout.get("holdout_candidate_count"),
        },
        "before_digest": hashlib.sha256(before).hexdigest() if before else None,
        "after_digest": hashlib.sha256(before).hexdigest() if before else None,
        "source_apply": False,
        "kb_promotion": status == "promoted",
    }
    if status != "promoted":
        return report

    catalog = _catalog(readiness=readiness, evaluator=evaluator, holdout=holdout, generated_at=report["generated_at"])
    encoded = (json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(catalog_file, encoded)
    reloaded = json.loads(catalog_file.read_text(encoding="utf-8"))
    if reloaded.get("status") != "active":
        _atomic_write(catalog_file, before)
        raise ValueError("promoted catalog did not reload as active")
    report["after_digest"] = hashlib.sha256(encoded).hexdigest()
    return report


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload


def _relative(root: Path, path: Path) -> str:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve().relative_to(root).as_posix()


def _atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
