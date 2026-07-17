"""Import external structured sources into staged KB candidates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .knowledge import official_docs_knowledge
from .knowledge_admission import build_kb_candidate


PYPI_API = "https://pypi.org/pypi/{package}/json"


ARCHETYPE_RULES = [
    {
        "rule_id": "schema_validation_library",
        "label": "schema/validation library",
        "signals": ["schema", "validation", "validator", "pydantic", "jsonschema", "marshmallow"],
        "first_slice": "schema_validation_contract_slice",
    },
    {
        "rule_id": "signing_token_utility",
        "label": "signing/token utility",
        "signals": ["sign", "signature", "serializer", "token", "dangerous"],
        "first_slice": "sign_verify_contract_slice",
    },
    {
        "rule_id": "docs_site_generator",
        "label": "documentation/static site generator",
        "signals": ["documentation", "markdown", "site", "mkdocs", "theme"],
        "first_slice": "site_page_render_slice",
    },
    {
        "rule_id": "cloud_api_sdk",
        "label": "cloud/API SDK",
        "signals": ["aws", "cloud", "sdk", "client", "endpoint", "service"],
        "first_slice": "sdk_service_call_slice",
    },
    {
        "rule_id": "media_processing_library",
        "label": "media processing library",
        "signals": ["image", "video", "media", "pillow", "moviepy", "ffmpeg"],
        "first_slice": "media_decode_transform_encode_slice",
    },
    {
        "rule_id": "async_protocol_runtime",
        "label": "async protocol runtime",
        "signals": ["async", "protocol", "websocket", "asgi", "trio", "uvicorn"],
        "first_slice": "async_protocol_event_slice",
    },
]


def fetch_pypi_metadata(package: str) -> dict[str, Any]:
    """Fetch PyPI JSON metadata for one package."""

    package = package.strip()
    if not package:
        raise ValueError("package must be non-empty")
    url = PYPI_API.format(package=quote(package))
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "cognitive-os-pypi-import"})
    with urlopen(request, timeout=10) as response:  # nosec: fixed PyPI API endpoint
        payload = json.loads(response.read().decode("utf-8"))
    info = dict(payload.get("info") or {})
    return {
        "source": "pypi_json",
        "package": package,
        "url": url,
        "name": info.get("name") or package,
        "version": info.get("version"),
        "summary": info.get("summary") or "",
        "description_content_type": info.get("description_content_type") or "",
        "classifiers": [str(item) for item in (info.get("classifiers") or [])],
        "project_urls": dict(info.get("project_urls") or {}),
        "requires_dist": [str(item) for item in (info.get("requires_dist") or [])],
        "keywords": str(info.get("keywords") or ""),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def pypi_candidate_from_metadata(metadata: dict[str, Any], *, source_case_status: str = "confirmed") -> dict[str, Any] | None:
    """Convert PyPI metadata into a staged architecture-rule candidate."""

    match = infer_archetype_from_pypi(metadata)
    if match is None:
        return None
    package = str(metadata.get("package") or metadata.get("name") or "")
    proposed_record = {
        "record_type": "project_archetype_rule",
        "rule_id": match["rule_id"],
        "archetype": match["rule_id"],
        "label": match["label"],
        "role_scope": ["project_analyzer", "architect", "spec_writer"],
        "evidence_strength": "weak",
        "match": {
            "text_contains_any": _dedupe([package, *match["matched_signals"]]),
            "required_contains_any": [package],
            "min_score": 2,
        },
        "first_slice": {"name": match["first_slice"], "target_sources": ["central", "orchestrators", "broad"]},
        "candidate_origin": {"source": "pypi_json", "package": package},
    }
    return build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record=proposed_record,
        source_cases=[
            {
                "project": package,
                "status": source_case_status,
                "source": "pypi_json",
                "summary": metadata.get("summary"),
                "classifiers": metadata.get("classifiers", [])[:8],
                "project_urls": metadata.get("project_urls", {}),
            }
        ],
        teacher_reference=f"PyPI metadata suggests {match['label']} for {package}",
    )


def official_docs_fact_candidate(
    *,
    url: str,
    question: str,
    needed_for: str,
    role_scope: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap official docs evidence as a staged fact candidate."""

    result = official_docs_knowledge(url, question=question, needed_for=needed_for)
    artifact = result["knowledge_artifacts"][0]
    proposed_record = {
        "record_type": "official_docs_fact",
        "fact_id": _fact_id(url, question),
        "role_scope": role_scope or ["researcher", "architect", "spec_writer", "tester"],
        "evidence_strength": "weak",
        "source": "official_docs_fetch",
        "question": question,
        "needed_for": needed_for,
        "extracted_fact": artifact["extracted_fact"],
        "evidence": artifact["evidence"],
        "limitations": artifact["limitations"],
    }
    return build_kb_candidate(
        record_type="official_docs_fact",
        proposed_record=proposed_record,
        source_cases=[
            {
                "project": needed_for,
                "status": "confirmed",
                "source": "official_docs_fetch",
                "url": url,
                "question": question,
                "confidence": artifact["confidence"],
            }
        ],
        teacher_reference=f"Official docs evidence for {needed_for}: {question}",
    )


def infer_archetype_from_pypi(metadata: dict[str, Any]) -> dict[str, Any] | None:
    text = _metadata_text(metadata)
    candidates = []
    for rule in ARCHETYPE_RULES:
        found = [signal for signal in rule["signals"] if signal.lower() in text]
        if found:
            candidates.append({**rule, "matched_signals": found, "score": len(found)})
    if not candidates:
        return None
    candidates.sort(key=lambda row: (-int(row["score"]), str(row["rule_id"])))
    return candidates[0]


def _metadata_text(metadata: dict[str, Any]) -> str:
    parts = [
        str(metadata.get("package") or ""),
        str(metadata.get("name") or ""),
        str(metadata.get("summary") or ""),
        str(metadata.get("keywords") or ""),
        " ".join(str(item) for item in metadata.get("classifiers", [])),
        " ".join(str(item) for item in metadata.get("project_urls", {}).values()),
        " ".join(str(item) for item in metadata.get("requires_dist", [])),
    ]
    return " ".join(parts).lower()


def _dedupe(values: list[str]) -> list[str]:
    result = []
    for value in values:
        clean = str(value).strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _fact_id(url: str, question: str) -> str:
    return "docs_fact_" + str(abs(hash(f"{url}:{question}")))[:12]
