"""Primary title parser for the MVP."""

from __future__ import annotations

from html.parser import HTMLParser


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


def run(payload: dict[str, object]) -> dict[str, object]:
    html = str(payload["html"])
    if "__SIMULATE_IMPORT_ERROR__" in html:
        raise ImportError("simulated stale parser dependency")
    parser = _TitleParser()
    parser.feed(html)
    title = " ".join(part.strip() for part in parser.parts if part.strip())
    return {"title": title or "untitled"}

