from __future__ import annotations

import re
from typing import Literal

DeadlineClass = Literal["final", "priority", "unverified"]

PRIMARY_EVIDENCE = frozenset({"official_institution", "official_plus_email"})


def primary_source_verified(confidence: object) -> bool:
    return str(confidence or "") in PRIMARY_EVIDENCE


def classify_deadline_note(note: object) -> DeadlineClass:
    normalized = " ".join(str(note or "").casefold().split())
    if re.search(r"\bpriority\b|\bbest[- ]consideration\b", normalized):
        return "priority"
    uncertain = (
        "index only",
        "not independently confirmed",
        "not independently established",
        "not verified",
        "unconfirmed deadline",
        "deadline not confirmed",
        "deadline unknown",
        "no fixed deadline",
        "rolling until",
    )
    if any(phrase in normalized for phrase in uncertain):
        return "unverified"
    if re.search(r"\bfinal\b|\bdeadline\b|\bclosing date\b|\bapply by\b", normalized):
        return "final"
    return "unverified"

MONITOR_STATUS_RANK = {
    "anchor_present": 0,
    "not_checked": 0,
    "unavailable": 2,
    "response_too_large": 2,
    "disallowed_host": 3,
    "unsafe_redirect": 3,
    "review_source_changed": 4,
    "contradiction_deadline_mismatch": 5,
    "contradiction_closed_portal": 5,
}


def summarize_watch_statuses(observations: list[dict]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for item in observations:
        application = item.get("application_id") or item.get("id")
        status = str(item.get("status") or "")
        if not application or not status:
            continue
        current = selected.get(application, "")
        if MONITOR_STATUS_RANK.get(status, 1) > MONITOR_STATUS_RANK.get(current, -1):
            selected[application] = status
    return selected
