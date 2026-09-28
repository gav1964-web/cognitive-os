"""Quality modes for bounded L4.5 model usage."""

from __future__ import annotations

from typing import Any


MODEL_QUALITY_MODES: dict[str, dict[str, Any]] = {
    "deterministic": {
        "use_model": False,
        "requires_human_review": False,
        "trusted_for_action": False,
        "description": "Use deterministic proposal generation only.",
    },
    "model_propose_only": {
        "use_model": True,
        "requires_human_review": False,
        "trusted_for_action": False,
        "description": "Use model as a bounded semantic proposal source; L4.0 validation still decides.",
    },
    "model_with_human_review": {
        "use_model": True,
        "requires_human_review": True,
        "trusted_for_action": False,
        "description": "Use model proposal and require explicit human review before admission or implementation.",
    },
    "blocked_model_untrusted": {
        "use_model": False,
        "requires_human_review": True,
        "trusted_for_action": False,
        "description": "Do not call model; record that the model path is intentionally blocked.",
    },
}


def resolve_model_quality_mode(mode: str | None, *, use_model_flag: bool = False) -> dict[str, Any]:
    selected = mode or ("model_propose_only" if use_model_flag else "deterministic")
    if selected not in MODEL_QUALITY_MODES:
        raise ValueError(f"unknown L4.5 model quality mode: {selected}")
    policy = dict(MODEL_QUALITY_MODES[selected])
    policy["mode"] = selected
    return policy
