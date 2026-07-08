"""Interrupt packet creation."""

from __future__ import annotations

import json
from pathlib import Path

from .checkpoint import hash_payload
from .models import RuntimeFailure


def build_interrupt(
    *,
    root: Path,
    pipeline_id: str,
    failed_node_id: str,
    capability_id: str,
    failure: RuntimeFailure,
    state_ref: str,
    capability_status: str,
    suggested_actions: list[str],
    input_payload: dict[str, object],
    version_hash: str,
) -> dict[str, object]:
    packet = {
        "type": "CRITICAL_INTERRUPT",
        "pipeline_id": pipeline_id,
        "failed_node_id": failed_node_id,
        "capability_id": capability_id,
        "error_class": failure.error_class,
        "error_fingerprint": {
            "exception_type": failure.exception_type,
            "traceback_hash": failure.traceback_hash,
            "input_hash": hash_payload(input_payload),
            "version_hash": version_hash,
        },
        "state_ref": state_ref,
        "capability_status": capability_status,
        "suggested_actions": suggested_actions,
    }
    out_dir = root / "artifacts" / "interrupts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{state_ref}.interrupt.json"
    out_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return packet

