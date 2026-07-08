"""Checkpoint persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import ExecutionContext


def save_checkpoint(root: Path, context: ExecutionContext, *, registry_hash: str) -> str:
    checkpoint_id = f"chk_{context.pipeline.id}_{_short_hash(context.current_node or 'none')}"
    path = root / "artifacts" / "checkpoints" / f"{checkpoint_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checkpoint_id": checkpoint_id,
        "pipeline_id": context.pipeline.id,
        "pipeline_version": context.pipeline.version,
        "state": context.state,
        "current_node": context.current_node,
        "completed_nodes": context.completed_nodes,
        "node_outputs": {
            node_id: {"output": output, "output_hash": hash_payload(output)}
            for node_id, output in context.node_outputs.items()
        },
        "root_input": context.root_input,
        "input_hash": hash_payload(context.root_input),
        "registry_hash": registry_hash,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return checkpoint_id


def load_checkpoint(root: Path, checkpoint_id: str) -> dict[str, Any]:
    path = root / "artifacts" / "checkpoints" / f"{checkpoint_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def hash_payload(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
