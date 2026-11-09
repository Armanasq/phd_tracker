from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlsplit

FIELDS: dict[str, float] = {
    "id": 9.0,
    "name": 5.0,
    "topic": 4.0,
    "faculty": 3.0,
    "country": 2.4,
    "next_step": 2.2,
    "fit": 2.0,
    "eligibility": 1.8,
    "funding": 1.6,
    "documents": 1.4,
    "document_states": 1.2,
    "blockers": 1.3,
    "status": 0.8,
    "priority": 0.6,
}
STOPWORDS = frozenset({
    "a", "about", "all", "an", "and", "are", "at", "be", "can", "could",
    "do", "does", "for", "from", "give", "have", "how", "i", "in", "is",
    "it", "me", "my", "of", "on", "or", "our", "please", "show", "should",
    "that", "the", "their", "these", "this", "to", "us", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "you",
})
EVIDENCE_FIELDS = (
    "id", "name", "record_type", "country", "status", "verification",
    "deadline", "deadline_type", "deadline_kind", "deadline_time_verified",
    "source_url", "apply_url", "topic", "faculty", "fit", "funding",
    "eligibility", "documents", "document_states", "blockers", "next_step",
    "contact_status", "followup", "priority", "duplicate_submission_advisory",
)
CLOSED_STATUSES = frozenset({"archived", "withdrawn", "rejected", "submitted"})


def tokens(text: object) -> tuple[str, ...]:
    if not isinstance(text, str):
        return ()
    return tuple(dict.fromkeys(word for word in re.findall(r"[\w]+", text.casefold())
                               if len(word) >= 2 and word not in STOPWORDS))[:32]


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return value[:2400]
    if isinstance(value, dict):
        return " ".join(f"{key} {as_text(item)}" for key, item in list(value.items())[:30])
    if isinstance(value, (list, tuple)):
        return " ".join(as_text(item) for item in value[:30])
    if value is None:
        return ""
    return str(value)[:200]


def reference(record: dict[str, Any], matched_fields: list[str]) -> dict[str, Any]:
    source = str(record.get("source_url") or "")
    parts = urlsplit(source)
    source_url = source if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password else None
    return {
        "application_id": str(record.get("id", ""))[:120],
        "name": str(record.get("name", ""))[:180],
        "source_url": source_url,
        "verification": str(record.get("verification") or "unknown")[:80],
        "matched_fields": matched_fields[:6],
    }


def select_evidence(
    query: str,
    records: list[dict[str, Any]],
    *,
    application_id: str | None = None,
    today: date | None = None,
    limit: int = 7,
) -> dict[str, Any]:
    if not isinstance(query, str) or not 1 <= limit <= 15:
        raise ValueError("Invalid evidence query or result limit")
    by_id = {str(r.get("id")): r for r in records if isinstance(r, dict) and r.get("id")}
    if application_id:
        if application_id not in by_id:
            raise ValueError("Unknown application")
        record = by_id[application_id]
        return {
            "method": "selected_application",
            "matched_count": 1,
            "records": [{key: record.get(key) for key in EVIDENCE_FIELDS if key in record}],
            "references": [reference(record, ["selected_application"])],
        }

    words = tokens(query)
    indexed: list[tuple[dict[str, Any], dict[str, set[str]]]] = []
    counts: Counter[str] = Counter()
    for record in by_id.values():
        fields = {field: set(tokens(as_text(record.get(field)))) for field in FIELDS}
        indexed.append((record, fields))
        present = set().union(*fields.values())
        counts.update(set(words) & present)
    total = max(1, len(indexed))
    matches: list[tuple[float, dict[str, Any], list[str]]] = []
    for record, fields in indexed:
        contributions: dict[str, float] = {}
        for field, weight in FIELDS.items():
            overlapping = fields[field].intersection(words)
            if not overlapping:
                continue
            contributions[field] = weight * sum(
                math.log(1.0 + (total - counts[word] + 0.5) / (counts[word] + 0.5))
                for word in overlapping
            )
        if contributions:
            score = sum(contributions.values())
            matches.append((score, record, sorted(contributions, key=lambda name: (-contributions[name], name))))
    matches.sort(key=lambda row: (-row[0], str(row[1].get("deadline") or "9999"), str(row[1].get("id"))))
    method = "weighted_lexical"
    matched_count = len(matches)
    if matches:
        ranked = [(record, fields) for _, record, fields in matches[:limit]]
    else:
        method = "deadline_fallback"
        open_records = [record for record in by_id.values()
                        if record.get("record_type") == "tracked" and record.get("status") not in CLOSED_STATUSES]
        if today is not None:
            open_records = [record for record in open_records if not record.get("deadline")
                            or str(record["deadline"]) >= today.isoformat()]
        open_records.sort(key=lambda record: (str(record.get("deadline") or "9999-12-31"),
                                               str(record.get("id"))))
        ranked = [(record, []) for record in open_records[:limit]]
    return {
        "method": method,
        "matched_count": matched_count,
        "records": [{key: record.get(key) for key in EVIDENCE_FIELDS if key in record}
                    for record, _ in ranked],
        "references": [reference(record, fields) for record, fields in ranked],
    }
