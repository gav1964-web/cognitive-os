"""Documentation purpose extraction helpers."""

from __future__ import annotations

from typing import Any


NON_PURPOSE_HEADINGS = {
    "agents.md",
    "changes",
    "changelog",
    "claude.md",
    "contributing",
    "contributors",
    "contributors (alphabetical order)",
    "design considerations",
    "license",
}


def docs_text(files: dict[str, Any]) -> str:
    texts = []
    for item in sorted(files.get("files", []), key=_doc_priority):
        if str(item.get("path", "")).lower().endswith((".md", ".rst", ".txt")):
            texts.append(str(item.get("text", ""))[:3000])
    return "\n".join(texts).strip()


def purpose_heading(docs: str) -> str:
    lines = docs.splitlines()
    for index, line in enumerate(lines):
        heading = _heading_text(lines, index)
        if not heading:
            continue
        normalized = heading.lower().strip("` ")
        if normalized in NON_PURPOSE_HEADINGS or _non_purpose_heading(normalized):
            continue
        return heading
    return ""


def purpose_sentence(docs: str) -> str:
    lines = docs.splitlines()
    paragraph: list[str] = []
    seen_top_heading = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("##") and seen_top_heading and not paragraph:
            break
        if stripped.startswith("#"):
            seen_top_heading = True
            continue
        if stripped.startswith(("#", "[!", "![", "<", "|", ".. ", ":")) or set(stripped) <= {"=", "-", "~"}:
            continue
        if stripped.startswith(("-", "*", "1.", "2.", "3.", "**note**", "**NOTE**")):
            continue
        if _non_purpose_sentence(stripped.lower()):
            continue
        paragraph.append(stripped)
    text = " ".join(paragraph).strip()
    if not text:
        return ""
    for separator in (". ", ".\n"):
        if separator in text:
            return text.split(separator, 1)[0].strip() + "."
    return text[:240].strip()


def _doc_priority(item: dict[str, Any]) -> tuple[int, str]:
    path = str(item.get("path", "")).lower()
    name = path.rsplit("/", 1)[-1]
    if name.startswith("readme") and "/" not in path:
        return (0, path)
    if name.startswith("readme"):
        return (2, path)
    if path.startswith(("docs/", "examples/", "tests/")):
        return (3, path)
    return (1, path)


def _heading_text(lines: list[str], index: int) -> str:
    line = lines[index].strip()
    if line.startswith("#"):
        return line.strip("# ").strip()
    if index + 1 < len(lines) and line and set(lines[index + 1].strip()) <= {"=", "-", "~"}:
        return line
    return ""


def _non_purpose_heading(normalized: str) -> bool:
    return (
        "build backend" in normalized
        or normalized.startswith((".. ", "<", "</"))
        or "changelog" in normalized
        or "change notes" in normalized
    )


def _non_purpose_sentence(normalized: str) -> bool:
    return (
        "intentionally excludes" in normalized
        or normalized.startswith("what is not included")
        or normalized.startswith("the package excludes")
        or normalized.startswith("not included")
    )
