from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .store import Store

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DECISIONS = frozenset({"needs_follow_up", "reviewed_no_fact_change"})


def record_source_review(
    store: Store, *, observation_id: int, decision: str,
    note: str, expected_digest: str | None,
) -> dict[str, Any]:
    if type(observation_id) is not int or observation_id < 1:
        raise ValueError("Observation ID must be a positive integer")
    if decision not in _DECISIONS:
        raise ValueError("Unsupported source review decision")
    if not isinstance(note, str) or not 24 <= len(note.strip()) <= 1500:
        raise ValueError("Review note must contain 24–1500 characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in note):
        raise ValueError("Review note contains control characters")
    if expected_digest is not None and (
        not isinstance(expected_digest, str) or not _DIGEST.fullmatch(expected_digest)
    ):
        raise ValueError("Invalid expected source digest")

    item = store.db.execute(
        "SELECT id,application_id,source_url,content_sha256,drift "
        "FROM source_observations WHERE id=?", (observation_id,),
    ).fetchone()
    if item is None:
        raise ValueError("Unknown source observation")
    if item["content_sha256"] != expected_digest:
        raise ValueError("Source digest mismatch; reload before reviewing")
    if decision == "reviewed_no_fact_change" and item["drift"] != "source_bytes_changed_needs_review":
        raise ValueError("No-material-change decision requires an observed byte change")

    normalized_note = note.strip()
    previous = store.db.execute(
        "SELECT id,decision,note,reviewed_at FROM source_observation_reviews "
        "WHERE observation_id=? ORDER BY id DESC LIMIT 1", (observation_id,),
    ).fetchone()
    if previous is not None and previous["decision"] == decision and previous["note"] == normalized_note:
        return {
            "id": previous["id"], "observation_id": observation_id,
            "decision": decision, "reviewed_at": previous["reviewed_at"],
            "authority": "owner_attestation_only", "reused": True,
        }

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with store.db:
        cursor = store.db.execute(
            "INSERT INTO source_observation_reviews("
            "observation_id,application_id,source_url,source_sha256,decision,note,reviewed_at"
            ") VALUES(?,?,?,?,?,?,?)",
            (observation_id, item["application_id"], item["source_url"],
             item["content_sha256"], decision, normalized_note, timestamp),
        )
        store._audit("source:review_noted", item["application_id"])
    return {
        "id": cursor.lastrowid, "observation_id": observation_id,
        "decision": decision, "reviewed_at": timestamp,
        "authority": "owner_attestation_only", "reused": False,
    }
