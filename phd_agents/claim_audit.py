from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

_LINK = re.compile(r"\[(source|claim):([A-Za-z0-9][A-Za-z0-9:_.-]{0,119})\]")
_TRUSTED_SOURCE_STATES = frozenset({"source_verified", "owner_verified"})


def _safe_primary_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname) and not (
        parsed.username or parsed.password
    )


def audit_generated_claims(
    response: str, source_refs: list[dict[str, Any]], claim_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(response, str) or len(response) > 20000:
        raise ValueError("Model answer exceeds claim-audit bounds")
    if not isinstance(source_refs, list) or not isinstance(claim_registry, list):
        raise ValueError("Claim-audit evidence must be lists")
    sources = {
        ref["application_id"]: ref
        for ref in source_refs[:15]
        if isinstance(ref, dict) and isinstance(ref.get("application_id"), str)
    }
    claims = {
        item["id"]: item
        for item in claim_registry[:20]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    links: list[dict[str, object]] = []
    unknown = unverified = linked = 0
    for match in list(_LINK.finditer(response))[:100]:
        kind, identity = match.group(1), match.group(2)
        selected = sources.get(identity) if kind == "source" else claims.get(identity)
        if selected is None:
            status = "unknown_reference"
            unknown += 1
        elif kind == "source":
            status = (
                "linked_to_reviewed_record" if
                selected.get("verification") in _TRUSTED_SOURCE_STATES
                and _safe_primary_url(selected.get("source_url"))
                else "linked_to_unverified_record"
            )
            if status == "linked_to_unverified_record":
                unverified += 1
            else:
                linked += 1
        else:
            status = (
                "linked_to_reviewed_record" if
                selected.get("status") == "primary_confirmed"
                and _safe_primary_url(selected.get("source_url"))
                and bool(selected.get("excerpt"))
                else "linked_to_unverified_record"
            )
            if status == "linked_to_unverified_record":
                unverified += 1
            else:
                linked += 1
        links.append({"kind": kind, "id": identity, "status": status})
    blocks = [
        block.strip() for block in response.splitlines()
        if block.strip() and not block.lstrip().startswith(("#", "---"))
    ]
    missing = sum(not _LINK.search(block) for block in blocks)
    return {
        "schema_version": 1,
        "status": "requires_human_fact_check",
        "reference_links": links,
        "linked_to_reviewed_records": linked,
        "linked_to_unverified_records": unverified,
        "unknown_reference_links": unknown,
        "unlinked_text_blocks": missing,
        "cited_source_record_count": len(sources),
        "cited_owner_evidence_count": len(claims),
        "semantic_entailment_verified": False,
        "explanation": "Citations only match supplied record IDs and review states; they do not prove the model statement is entailed by the cited primary source.",
    }
