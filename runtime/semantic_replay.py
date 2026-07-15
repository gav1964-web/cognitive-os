"""Replay artifacts for L4.0/L4.5 semantic proposal runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_semantic_replay_record(
    *,
    request: dict[str, Any],
    proposal: dict[str, Any],
    validation: dict[str, Any],
    evidence_pack: dict[str, Any] | None = None,
    model_quality_mode: str = "deterministic",
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hardening = dict(proposal.get("hardening", {})) if isinstance(proposal.get("hardening"), dict) else {}
    return {
        "artifact_type": "SemanticProposalReplay",
        "status": "recorded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_quality_mode": model_quality_mode,
        "request": request,
        "evidence_pack": evidence_pack,
        "proposal": proposal,
        "hardening": {
            "raw_model_output_used": bool(hardening.get("raw_model_output_used")),
            "forbidden_actions_stripped": bool(hardening.get("forbidden_actions_stripped")),
            "schema_normalized": bool(hardening.get("schema_normalized")),
            "model_error": hardening.get("model_error"),
            "fallback": hardening.get("fallback"),
        },
        "validation": validation,
        "outcome": outcome or _outcome(validation),
        "audit": {
            "proposal_status": proposal.get("status"),
            "hypothesis_type": proposal.get("hypothesis_type"),
            "l4_status": validation.get("status"),
            "accepted_action": validation.get("accepted_action"),
        },
    }


def write_semantic_replay_record(root: Path, record: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "semantic_replays"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    hypothesis = str(dict(record.get("proposal", {})).get("hypothesis_type") or "semantic")
    path = out_dir / f"semantic_replay_{hypothesis}_{stamp}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _outcome(validation: dict[str, Any]) -> dict[str, Any]:
    decision = dict(validation.get("decision", {})) if isinstance(validation.get("decision"), dict) else {}
    return {
        "status": validation.get("status"),
        "next_action": decision.get("next_action") or validation.get("accepted_action"),
        "reason_code": decision.get("reason_code"),
    }
