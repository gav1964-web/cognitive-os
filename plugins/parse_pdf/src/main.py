"""PDF text extraction with an optional production backend.

The plugin prefers ``pypdf`` when it is available in the runtime environment and
falls back to a small deterministic parser for simple text-like PDFs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def run(payload: dict[str, object]) -> dict[str, object]:
    path = Path(str(payload["path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("parse_pdf path must be workspace-relative and scoped")
    if not path.exists() or not path.is_file():
        raise ValueError("parse_pdf path must point to an existing file")
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError("parse_pdf input is not a PDF document")
    pypdf_result = _extract_with_pypdf(path)
    if pypdf_result is not None:
        return pypdf_result
    text = _extract_text(data)
    page_count = max(1, data.count(b"/Type /Page"))
    return {"text": text, "page_count": page_count, "backend": "builtin"}


def _extract_with_pypdf(path: Path) -> dict[str, Any] | None:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception:
        return None

    reader = PdfReader(str(path))
    pages = list(reader.pages)
    chunks = []
    for page in pages:
        text = page.extract_text() or ""
        text = " ".join(text.split())
        if text:
            chunks.append(text)
    return {"text": " ".join(chunks), "page_count": max(1, len(pages)), "backend": "pypdf"}


def _extract_text(data: bytes) -> str:
    chunks = []
    for match in re.finditer(rb"\(([^()]*)\)", data):
        chunk = match.group(1).decode("utf-8", errors="ignore").strip()
        if chunk:
            chunks.append(chunk)
    if not chunks:
        decoded = data.decode("utf-8", errors="ignore")
        chunks = re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.;:!?_-]{2,}", decoded)
    return " ".join(" ".join(chunks).split())
