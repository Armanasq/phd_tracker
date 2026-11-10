from __future__ import annotations

import hashlib
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

EXCERPT_LIMIT = 24_000
_IGNORED = frozenset({"head", "script", "style", "template", "svg", "noscript", "iframe"})
_BLOCK = frozenset({
    "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
    "hr", "li", "main", "ol", "p", "section", "table", "td", "th", "tr", "ul",
})

_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
_HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*(?:!important\s*)?(?:;|$)", re.I)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, bool]] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        hidden = (
            tag in _IGNORED
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").strip().casefold() == "true"
            or bool(_HIDDEN_STYLE.search(attributes.get("style") or ""))
        )
        if tag not in _VOID:
            self.stack.append((tag, hidden))
            if hidden:
                self.hidden_depth += 1
        if not self.hidden_depth and tag in _BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        for position in range(len(self.stack) - 1, -1, -1):
            if self.stack[position][0] == tag:
                self.hidden_depth -= sum(hidden for _, hidden in self.stack[position:])
                del self.stack[position:]
                break
        if not self.hidden_depth and tag in _BLOCK:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
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
