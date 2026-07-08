"""Convert a bounded Markdown subset to RTF."""

from __future__ import annotations

import re


def run(payload: dict[str, object]) -> dict[str, object]:
    markdown = str(payload["markdown"])
    body = _blocks(markdown)
    return {"rtf": "{\\rtf1\\ansi\\deff0\n" + body + "\n}"}


def _blocks(markdown: str) -> str:
    rows = []
    in_code = False
    code_rows = []
    for raw in markdown.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                rows.append(_paragraph("\\fmodern " + _escape("\n".join(code_rows)), before=120, after=120))
                code_rows = []
            in_code = not in_code
            continue
        if in_code:
            code_rows.append(line)
            continue
        if not line.strip():
            continue
        rows.append(_block(line))
    if code_rows:
        rows.append(_paragraph("\\fmodern " + _escape("\n".join(code_rows)), before=120, after=120))
    return "\n".join(rows)


def _block(line: str) -> str:
    heading = re.match(r"^(#{1,6})\s+(.*)$", line)
    if heading:
        level = len(heading.group(1))
        size = max(24, 44 - (level * 4))
        return _paragraph(f"\\b\\fs{size} {_inline(heading.group(2))}\\b0", after=160)
    quote = re.match(r"^>\s?(.*)$", line)
    if quote:
        return _paragraph(f"\\li360\\i {_inline(quote.group(1))}\\i0", before=80, after=80)
    bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
    if bullet:
        return _paragraph("\\li360\\fi-180 " + _escape(chr(8226)) + " " + _inline(bullet.group(1)))
    ordered = re.match(r"^\s*(\d+)[.)]\s+(.*)$", line)
    if ordered:
        return _paragraph(f"\\li360\\fi-180 {ordered.group(1)}. {_inline(ordered.group(2))}")
    return _paragraph(_inline(line), after=80)


def _paragraph(text: str, *, before: int = 0, after: int = 0) -> str:
    spacing = f"\\sb{before}\\sa{after}" if before or after else ""
    return f"\\pard{spacing} {text}\\par"


def _inline(text: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    tokens = _code_tokens(text)
    escaped = _escape(tokens["text"])
    for key, value in tokens["values"].items():
        escaped = escaped.replace(_escape(key), "\\fmodern " + _escape(value) + "\\f0")
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"\\b \1\\b0", escaped)
    escaped = re.sub(r"__([^_]+)__", r"\\b \1\\b0", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\i \1\\i0", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"\\i \1\\i0", escaped)
    return escaped


def _code_tokens(text: str) -> dict[str, object]:
    values = {}

    def replace(match: re.Match[str]) -> str:
        key = f"@@CODE{len(values)}@@"
        values[key] = match.group(1)
        return key

    return {"text": re.sub(r"`([^`]+)`", replace, text), "values": values}


def _escape(text: str) -> str:
    rows = []
    for char in text:
        code = ord(char)
        if char in {"\\", "{", "}"}:
            rows.append("\\" + char)
        elif char == "\n":
            rows.append("\\line ")
        elif code > 127:
            signed = code if code < 32768 else code - 65536
            rows.append(f"\\u{signed}?")
        else:
            rows.append(char)
    return "".join(rows)
