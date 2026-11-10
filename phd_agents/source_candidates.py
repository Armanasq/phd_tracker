from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from .source_claims import observation_text
from .source_text import normalize_excerpt
from .store import Store

_MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_PATTERNS = (
    re.compile(r"(?<![\d/-])(?P<year>20\d{2})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])(?![\d/-])"),
    re.compile(r"(?<![\w/])(?P<day>[0-3]?\d)(?:st|nd|rd|th)?\s+(?P<month>" + _MONTH + r")\.?,?\s+(?P<year>20\d{2})(?!\d)", re.I),
    re.compile(r"(?<![\w/])(?P<month>" + _MONTH + r")\.?\s+(?P<day>[0-3]?\d)(?:st|nd|rd|th)?,?\s+(?P<year>20\d{2})(?!\d)", re.I),
)
_DEADLINE_LANGUAGE = re.compile(
    r"\b(?:deadline|closing date|closes? on|applications? close|"
    r"applications? must be received|apply by|submit by|submission closes?|"
    r"last date to apply|final date to apply)\b", re.I,
)
_MAX_CANDIDATES = 25
_MAX_TEXT = 24_000


def extract_date_candidates(
    text: str, *, source_url: str, application_id: str, observed_at: str,
    source_digest: str, text_digest: str, source_truncated: bool = False,
) -> dict[str, Any]:
    if not isinstance(text, str) or len(text) > _MAX_TEXT or not isinstance(source_truncated, bool):
        raise ValueError("Date candidates require bounded captured source text")
    if normalize_excerpt(text) != text:
        raise ValueError("Source text must be in its stored normalized form")
    if not isinstance(source_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", source_digest):
        raise ValueError("Source candidate requires a captured byte digest")
    if not isinstance(text_digest, str) or hashlib.sha256(text.encode("utf-8")).hexdigest() != text_digest and not source_truncated:
        raise ValueError("Full retained source text must match the captured text digest")
    matches: list[tuple[int, int, str]] = []
    for pattern in _DATE_PATTERNS:
        for found in pattern.finditer(text):
            try:
                month_token = found.group("month")
                month = int(month_token) if month_token.isdigit() else _MONTHS.index(month_token.lower()[:3]) + 1
                parsed = date(int(found.group("year")), month, int(found.group("day")))
            except (ValueError, IndexError):
                continue
            if not (2020 <= parsed.year <= 2099):
                continue
            if any(start < found.end() and found.start() < end for start, end, _ in matches):
                continue
            matches.append((found.start(), found.end(), parsed.isoformat()))
    matches.sort(key=lambda item: (item[0], item[1]))
    exceeded = len(matches) > _MAX_CANDIDATES
    results = []
    for start, end, iso in matches[:_MAX_CANDIDATES]:
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end]
        detected = bool(_DEADLINE_LANGUAGE.search(context))
        quote_start = max(0, start - 110)
        quote_end = min(len(text), end + 110)
        quote = text[quote_start:quote_end]
        if len(quote) > 320:
            quote = quote[:320]
        results.append({
            "schema_version": 1,
            "application_id": application_id,
            "source_url": source_url,
            "observation_time": observed_at,
            "source_digest": source_digest,
            "visible_text_digest": text_digest,
            "span_start": start,
            "span_end": end,
            "source_location": "normalized_visible_text_characters",
            "date_mention": text[start:end],
            "normalized_date": iso,
            "candidate_type": "deadline" if detected else "other",
            "context_signal": "deadline_language_near_date" if detected else "date_mention_only",
            "exact_quote": quote,
            "quote_digest": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "review_status": "unverified_candidate_no_auto_promotion",
        })
    deadline_dates = {item["normalized_date"] for item in results if item["candidate_type"] == "deadline"}
    for item in results:
        item["multiple_deadline_dates"] = len(deadline_dates) > 1
    return {
        "schema_version": 1,
        "application_id": application_id,
        "source_url": source_url,
        "observation_time": observed_at,
        "candidates": results,
        "candidate_count": len(results),
        "ambiguous_deadline_dates": len(deadline_dates) > 1,
        "truncated_source_excerpt": source_truncated,
        "candidate_limit_exceeded": exceeded,
        "scan_complete": not source_truncated and not exceeded,
        "semantic_claim_verified": False,
        "status": "review_candidates_only",
        "notice": "Parsed date mentions are not verified deadlines or proof that a portal is open. "
        "Month-name and ISO dates are supported. Ambiguous numeric dates and timezone assumptions are excluded.",
    }


def source_date_candidates(store: Store, observation_id: int) -> dict[str, Any]:
    source = observation_text(store, observation_id)
    if source["status"] != "fetched" or not source["visible_text_sha256"]:
        raise ValueError("Date candidates require an observed, captured source text")
    return {
        "observation_id": observation_id,
        **extract_date_candidates(
            source["visible_text"],
            source_url=source["source_url"],
            application_id=source["application_id"],
            observed_at=source["observed_at"],
            source_digest=source["content_sha256"],
            text_digest=source["visible_text_sha256"],
            source_truncated=source["visible_text_truncated"],
        ),
    }
