"""Shared defaults for the external Level 4 model profile."""

from __future__ import annotations

import os


DEFAULT_L4_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_L4_MODEL = "GigaChat-Pro"


def l4_base_url() -> str:
    return os.environ.get("COGNITIVE_OS_L4_BASE_URL", DEFAULT_L4_BASE_URL)


def l4_model() -> str:
    return os.environ.get("COGNITIVE_OS_L4_MODEL", DEFAULT_L4_MODEL)
