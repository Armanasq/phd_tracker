from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .source_text import normalize_excerpt
from .store import Store

CLAIM_TYPES = frozenset({"deadline", "eligibility", "funding", "documents", "recruitment", "other"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def observation_text(store: Store, observation_id: int) -> dict[str, Any]:
    if type(observation_id) is not int or observation_id <= 0:
        raise ValueError("Observation ID must be a positive integer")
    row = store.db.execute(
        "SELECT id,application_id,source_url,observed_at,status,content_sha256,"
        "visible_text_excerpt,visible_text_sha256,visible_text_truncated,text_drift "
        "FROM source_observations WHERE id=?", (observation_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown source observation")
    return {
        "id": row["id"], "application_id": row["application_id"],
        "source_url": row["source_url"], "observed_at": row["observed_at"],
        "status": row["status"], "content_sha256": row["content_sha256"],
        "visible_text": row["visible_text_excerpt"] or "",
        "visible_text_sha256": row["visible_text_sha256"],
        "visible_text_truncated": bool(row["visible_text_truncated"]),
        "text_drift": row["text_drift"],
        "proof_level": "fetched_visible_text_not_verified_institutional_fact",
    }


def capture_source_claim(
    store: Store, *, observation_id: int, claim_type: str,
    quote: str, candidate_value: str, expected_digest: str,
) -> dict[str, Any]:
    if claim_type not in CLAIM_TYPES:
        raise ValueError("Unsupported claim type")
    if not isinstance(expected_digest, str) or not _DIGEST.fullmatch(expected_digest):
        raise ValueError("Expected digest must be the exact observed content hash")
    if not isinstance(quote, str) or not 20 <= len(quote) <= 320:
        raise ValueError("Exact source quote must contain 20–320 characters")
    if not isinstance(candidate_value, str) or not 1 <= len(candidate_value.strip()) <= 160:
        raise ValueError("Candidate value must contain 1–160 characters")
    value = candidate_value.strip()
    if any(ord(char) < 32 and char not in "\t\n" for char in quote + value):
        raise ValueError("Source claim contains control characters")
    observed = observation_text(store, observation_id)
    if observed["status"] != "fetched" or not observed["visible_text_sha256"]:
        raise ValueError("Cannot cite an observation without captured visible source text")
    if observed["content_sha256"] != expected_digest:
        raise ValueError("Observation changed; reload the primary-source evidence")
    needle = normalize_excerpt(quote)
    if needle not in observed["visible_text"]:
        raise ValueError("Exact quotation is absent from the captured source text")
    if len(needle) < 20:
        raise ValueError("Source quote is too short after normalization")
    quoted_digest = hashlib.sha256(needle.encode("utf-8")).hexdigest()
    recorded = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with store.db:
        store.db.execute(
            "INSERT OR IGNORE INTO source_claims("
            "observation_id,application_id,source_url,source_digest,claim_type,"
            "exact_quote,candidate_value,quote_digest,captured_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (
                observation_id, observed["application_id"], observed["source_url"],
                expected_digest, claim_type, needle, value, quoted_digest, recorded,
            ),
        )
        row = store.db.execute(
            "SELECT id,observation_id,application_id,source_url,source_digest,"
            "claim_type,exact_quote,candidate_value,quote_digest,captured_at,verification "
            "FROM source_claims WHERE observation_id=? AND claim_type=? "
            "AND quote_digest=? AND candidate_value=?",
            (observation_id, claim_type, quoted_digest, value),
        ).fetchone()
        store._audit("source:quote_captured", observed["application_id"])
    return dict(row)


def source_claims(store: Store, *, limit: int = 200) -> list[dict[str, Any]]:
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Source claim list limit must be 1–500")
    return [dict(row) for row in store.db.execute(
        "SELECT id,observation_id,application_id,source_url,source_digest,"
        "claim_type,exact_quote,candidate_value,quote_digest,captured_at,verification "
        "FROM source_claims ORDER BY id DESC LIMIT ?", (limit,),
    ).fetchall()]
