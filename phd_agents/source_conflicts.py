from __future__ import annotations

from collections import defaultdict
from typing import Any

from .store import Store


def source_claim_disagreements(store: Store, *, limit: int = 500) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Disagreement sample limit must be 1–1000")
    rows = store.db.execute(
        "SELECT c.id,c.application_id,c.claim_type,c.candidate_value,c.source_url,"
        "c.source_digest,c.observation_id,c.captured_at,c.verification,"
        "r.decision AS owner_review_decision "
        "FROM source_claims AS c LEFT JOIN source_claim_reviews AS r ON "
        "r.id=(SELECT MAX(v.id) FROM source_claim_reviews AS v WHERE v.claim_id=c.id) "
        "ORDER BY c.id DESC LIMIT ?",
        (limit + 1,),
    ).fetchall()
    truncated = len(rows) > limit
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows[:limit]:
        item = dict(row)
        grouped[(item["application_id"], item["claim_type"])].append(item)
    conflicts = []
    for (application_id, claim_type), entries in grouped.items():
        distinct = {item["candidate_value"].strip().casefold() for item in entries}
        if len(distinct) < 2:
            continue
        unique_urls = {item["source_url"] for item in entries}
        observed = [
            {
                "claim_id": item["id"],
                "observation_id": item["observation_id"],
                "candidate_value": item["candidate_value"],
                "source_url": item["source_url"],
                "source_digest": item["source_digest"],
                "captured_at": item["captured_at"],
                "owner_review_decision": item["owner_review_decision"],
                "verification": item["verification"],
            }
            for item in sorted(entries, key=lambda row: row["id"], reverse=True)
        ]
        conflicts.append({
            "application_id": application_id,
            "claim_type": claim_type,
            "distinct_candidate_values": len(distinct),
            "claim_count": len(entries),
            "source_count": len(unique_urls),
            "source_pattern": (
                "same_source_versions_disagree" if len(unique_urls) == 1
                else "cross_source_candidate_disagreement"
            ),
            "status": "manual_disagreement_review_required",
            "semantic_claim_verified": False,
            "claims": observed[:30],
            "claims_limited": len(observed) > 30,
        })
    conflicts.sort(key=lambda item: (-item["claim_count"], item["application_id"], item["claim_type"]))
    return {
        "schema_version": 1,
        "scope": "private_owner_candidate_disagreements",
        "scanned_claims": min(len(rows), limit),
        "sample_truncated": truncated,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "semantic_claim_verified": False,
        "notice": "Different proposed values are review signals, not proven contradictions. "
        "Earlier site versions, separate application rounds, and rejected owner interpretations remain visible. "
        "This report never resolves an institutional fact or modifies an applicant record.",
    }
