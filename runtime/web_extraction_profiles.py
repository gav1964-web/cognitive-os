"""Configured web extraction profiles used by Stage 2 routing."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "config" / "web_extraction_profiles.json"


class WebExtractionProfilesError(RuntimeError):
    """Raised when web extraction profile configuration is invalid."""


@lru_cache(maxsize=1)
def load_web_extraction_profiles(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else PROFILES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "web_extraction_profiles.v1":
        raise WebExtractionProfilesError("web extraction profiles must use schema_version web_extraction_profiles.v1")
    if payload.get("status") != "active":
        raise WebExtractionProfilesError("web extraction profiles must be active")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise WebExtractionProfilesError("profiles must be a non-empty list")
    for row in profiles:
        _validate_profile(row)
    return payload


def known_web_extraction_hosts(*, target_kind: str | None = None, profiles: dict[str, Any] | None = None) -> list[str]:
    payload = profiles or load_web_extraction_profiles()
    hosts: list[str] = []
    for row in payload.get("profiles", []):
        if target_kind and str(row.get("target_kind")) != target_kind:
            continue
        hosts.append(str(row.get("host")))
    return hosts


def has_known_web_extraction_profile(
    prompt: str,
    *,
    target_kind: str,
    profiles: dict[str, Any] | None = None,
) -> bool:
    hosts = _hosts_from_prompt(prompt)
    if not hosts:
        return False
    known = set(known_web_extraction_hosts(target_kind=target_kind, profiles=profiles))
    return any(_host_matches(host, known_host) for host in hosts for known_host in known)


def _validate_profile(row: Any) -> None:
    if not isinstance(row, dict):
        raise WebExtractionProfilesError("profile must be object")
    for field in ("host", "target_kind", "base_url", "link_markers", "evidence"):
        if field not in row:
            raise WebExtractionProfilesError(f"profile requires {field}")
    if not isinstance(row.get("link_markers"), list) or not row.get("link_markers"):
        raise WebExtractionProfilesError("profile link_markers must be a non-empty list")
    if not isinstance(row.get("evidence"), list) or not row.get("evidence"):
        raise WebExtractionProfilesError("profile evidence must be a non-empty list")


def _hosts_from_prompt(prompt: str) -> list[str]:
    hosts: list[str] = []
    for token in re.findall(r"https?://[^\s)>,]+|(?:[a-z0-9-]+\.)+[a-z]{2,}", prompt.lower()):
        parsed = urlparse(token if "://" in token else "https://" + token)
        host = (parsed.netloc or parsed.path).split("/", 1)[0]
        host = host.removeprefix("www.")
        if host:
            hosts.append(host)
    return hosts


def _host_matches(host: str, known_host: str) -> bool:
    known = known_host.removeprefix("www.").lower()
    current = host.removeprefix("www.").lower()
    return current == known or current.endswith("." + known)
