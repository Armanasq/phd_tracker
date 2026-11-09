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
    return "final"
