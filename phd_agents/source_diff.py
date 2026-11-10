from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .source_claims import observation_text
from .store import Store

_MAX_TOKENS = 2500
_MAX_CHANGES = 40
_TOPICS = {
    "deadline": ("deadline", "closing", "cutoff", "cut-off", "due date", "applications close", "application closes", "apply by"),
    "eligibility": ("eligible", "eligibility", "admission", "requirement", "residency"),
    "funding": ("funding", "stipend", "scholarship", "tuition", "salary"),
    "documents": ("document", "transcript", "letter", "recommendation", "certificate"),
    "recruitment": ("vacancy", "position", "recruit", "application portal"),
}


def compare_source_text(store: Store, observation_id: int) -> dict[str, Any]:
    current = observation_text(store, observation_id)
    previous = store.db.execute(
        "SELECT id FROM source_observations WHERE application_id=? AND source_url=? "
        "AND id<? AND status='fetched' ORDER BY id DESC LIMIT 1",
        (current["application_id"], current["source_url"], current["id"]),
    ).fetchone()
    result: dict[str, Any] = {
        "schema_version": 1,
        "observation_id": observation_id,
        "application_id": current["application_id"],
        "source_url": current["source_url"],
        "current_sha256": current["content_sha256"],
        "previous_id": previous["id"] if previous else None,
        "status": "not_comparable",
        "changes": [],
        "possible_topics": [],
        "comparison_complete": False,
        "semantic_claim_verified": False,
        "notice": "Visible-text differences are review hints, not verification of an institutional requirement.",
    }
    if previous is None:
        result["status"] = "no_preceding_observation"
        return result
    earlier = observation_text(store, previous["id"])
    if (not current["visible_text_sha256"] or not earlier["visible_text_sha256"]
            or not current["visible_text"] or not earlier["visible_text"]):
        result["status"] = "text_unavailable"
        return result
    truncated = current["visible_text_truncated"] or earlier["visible_text_truncated"]
    if current["visible_text_sha256"] == earlier["visible_text_sha256"]:
        result["status"] = "visible_text_unchanged"
        result["comparison_complete"] = True
        return result
    if current["visible_text"] == earlier["visible_text"]:
        result["status"] = "changed_outside_retained_excerpt"
        return result
    old_words = earlier["visible_text"].split()
    new_words = current["visible_text"].split()
    shortened = len(old_words) > _MAX_TOKENS or len(new_words) > _MAX_TOKENS
    old_words, new_words = old_words[:_MAX_TOKENS], new_words[:_MAX_TOKENS]
    changes = []
    possible: set[str] = set()
    total = 0
    for operation, start_old, end_old, start_new, end_new in SequenceMatcher(
        None, old_words, new_words, autojunk=True
    ).get_opcodes():
        if operation == "equal":
            continue
        total += 1
        if len(changes) >= _MAX_CHANGES:
            continue
        before = " ".join(old_words[start_old:end_old])[:350]
        after = " ".join(new_words[start_new:end_new])[:350]
        preceding = " ".join(old_words[max(0, start_old - 7):start_old])[:140]
        following = " ".join(new_words[end_new:end_new + 7])[:140]
        combined = (preceding + " " + before + " " + after + " " + following).casefold()
        possible.update(kind for kind, terms in _TOPICS.items() if any(term in combined for term in terms))
        changes.append({
            "type": operation,
            "before": before,
            "after": after,
            "before_context": preceding,
            "after_context": following,
        })
    result.update({
        "status": "visible_text_changed",
        "changes": changes,
        "possible_topics": sorted(possible),
        "comparison_complete": not (truncated or shortened or total > len(changes)),
        "truncated": bool(truncated or shortened or total > len(changes)),
    })
    return result
