"""Documentation purpose extraction helpers."""

from __future__ import annotations

from typing import Any

from runtime.foundation_semantic_quality_policy import load_foundation_semantic_quality_policy


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
        path = str(item.get("path", "")).lower().replace("\\", "/")
        if _is_purpose_doc(path):
            texts.append(str(item.get("text", ""))[:3000])
    return "\n".join(texts).strip()


def _is_purpose_doc(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if not path.endswith((".md", ".rst", ".txt")):
        return False
    parts = path.split("/")
    if name.startswith(".") or any(part.startswith(".") for part in parts[:-1]):
        return False
    if any(part in {"changes", "changelog", "changelogs", "news", "towncrier"} for part in parts[:-1]):
        return False
    if name.startswith(("requirements", "constraints", "spelling_wordlist")) or name in {"license.txt", "notice.txt"}:
        return False
    return True


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
    skip_next_underline = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if skip_next_underline:
            skip_next_underline = False
            continue
        if not stripped:
            if paragraph:
                break
            continue
        next_stripped = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if next_stripped and set(next_stripped) <= {"=", "-", "~"}:
            seen_top_heading = True
            skip_next_underline = True
            continue
        if stripped.startswith("##") and seen_top_heading and not paragraph:
            heading = stripped.strip("# ").strip().lower()
            if heading in {"what is it?", "what is it", "overview", "about"}:
                continue
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


def descriptive_purpose_heading(docs: str) -> str:
    heading = purpose_heading(docs)
    lowered = heading.lower()
    words = [word for word in lowered.replace("-", " ").split() if word]
    if len(words) >= 6 or any(marker in lowered for marker in (" is a ", " is an ", " provides ", " for ")):
        return heading
    return ""


def _doc_priority(item: dict[str, Any]) -> tuple[int, str]:
    path = str(item.get("path", "")).lower()
    name = path.rsplit("/", 1)[-1]
    if name in {"readme.md", "readme.rst", "readme.txt"} and "/" not in path:
        return (0, path)
    if name.startswith("readme") and "/" not in path:
        return (2, path)
    if name in {"readme.md", "readme.rst", "readme.txt"}:
        return (3, path)
    if name.startswith("readme"):
        return (4, path)
    if path.startswith(("docs/", "examples/", "tests/")):
        return (5, path)
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
    project_policy = dict(load_foundation_semantic_quality_policy().get("project_analyzer") or {})
    marketing = [str(item).lower() for item in project_policy.get("marketing_purpose_markers", [])]
    return (
        "intentionally excludes" in normalized
        or normalized.startswith("what is not included")
        or normalized.startswith("the package excludes")
        or normalized.startswith("not included")
        or any(marker in normalized for marker in marketing)
    )
