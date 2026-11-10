from __future__ import annotations

import hashlib
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

EXCERPT_LIMIT = 24_000
_IGNORED = frozenset({"script", "style", "template", "svg", "noscript"})
_BLOCK = frozenset({
    "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
    "hr", "li", "main", "ol", "p", "section", "table", "td", "th", "tr", "ul",
})


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.excluded: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORED:
            self.excluded.append(tag)
        elif not self.excluded and tag in _BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.excluded:
            if tag == self.excluded[-1]:
                self.excluded.pop()
        elif tag in _BLOCK:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.excluded:
            self.parts.append(data)


def normalize_excerpt(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Source excerpt must be text")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def extract_visible_text(raw: bytes, media_type: str) -> dict[str, Any]:
    if not isinstance(raw, bytes) or len(raw) > 2_000_000:
        raise ValueError("Visible text input exceeds source transport limits")
    if media_type not in {"text/html", "text/plain"}:
        raise ValueError("Unsupported source content type")
    decoded = raw.decode("utf-8-sig", errors="replace")
    if media_type == "text/html":
        parser = _VisibleTextParser()
        parser.feed(decoded)
        parser.close()
        decoded = " ".join(parser.parts)
    canonical = normalize_excerpt(decoded)
    if not canonical:
        return {
            "visible_text_sha256": None,
            "visible_text_excerpt": "",
            "visible_text_truncated": False,
            "visible_text_length": 0,
        }
    return {
        "visible_text_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "visible_text_excerpt": canonical[:EXCERPT_LIMIT],
        "visible_text_truncated": len(canonical) > EXCERPT_LIMIT,
        "visible_text_length": len(canonical),
    }
