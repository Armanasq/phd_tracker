from __future__ import annotations

from datetime import date
from typing import Any

from .operations import evidence_conflicts

COMPLETED = {"offer", "rejected", "withdrawn", "archived", "blocked"}


def evidence_work_queue(
    records: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    references: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    today: date,
    *,
    limit: int = 80,
) -> dict[str, Any]:
    if not 1 <= limit <= 250:
        raise ValueError("Evidence queue limit must be in [1,250]")
    milestones_by_app: dict[str, list[dict[str, Any]]] = {}
    for item in milestones:
        milestones_by_app.setdefault(str(item.get("application_id")), []).append(item)
    result = []

    def add(record: dict[str, Any], kind: str, label: str, evidence: str, score: int,
            remaining: int | None, tab: str) -> None:
        rank = score + (40 if remaining is not None and 0 <= remaining <= 3 else
                        25 if remaining is not None and remaining <= 7 and remaining >= 0 else
                        12 if remaining is not None and remaining <= 30 and remaining >= 0 else 0)
        if record.get("priority") == "high":
            rank += 8
        result.append({
            "id": str(record["id"]) + ":" + kind + ":" + str(len(result)),
            "application_id": record["id"],
            "application": record.get("name") or record["id"],
            "kind": kind,
            "action": label,
            "proof_needed": evidence,
            "days_to_recorded_deadline": remaining,
            "heuristic_priority": rank,
            "target_section": tab,
            "source_url": record.get("source_url"),
            "status": "requires_owner_verification",
        })

    for r in records:
        if r.get("record_type") != "tracked" or r.get("status") in COMPLETED:
            continue
        remaining = None
        if r.get("deadline"):
            try:
                remaining = (date.fromisoformat(str(r["deadline"])) - today).days
            except ValueError:
                remaining = None
        if r.get("status") != "submitted":
            if remaining is None:
                add(r, "deadline_date", "Establish the official closing date",
                    "Authoritative application or admissions deadline and round", 95, remaining, "milestones")
            elif remaining >= 0:
                verified_cutoff = any(
                    m.get("kind") == "final" and m.get("date") == r.get("deadline")
                    and m.get("verification") == "primary_confirmed"
                    and m.get("time") and m.get("timezone") and m.get("source_url")
                    for m in milestones_by_app.get(r["id"], [])
                )
                if not verified_cutoff:
                    add(r, "cutoff_time", "Verify the exact submission cutoff",
                        "Official deadline time, IANA timezone, source link, and portal state",
                        82, remaining, "milestones")
            if r.get("verification") not in {"source_verified", "owner_verified"}:
                add(r, "primary_source", "Reconcile opportunity source verification",
                    "Primary-source program and vacancy evidence", 66, remaining, "evidence")
            documents = r.get("document_states") or {}
            unknown = [str(k) for k, state in documents.items() if state in {"unknown", "not_started", None}]
            if unknown:
                add(r, "documents", "Verify and prepare required application documents",
                    "Owner-confirmed readiness for " + ", ".join(sorted(unknown)[:8]),
                    52, remaining, "application")
        if r.get("status") == "submitted" and not r.get("receipt"):
            add(r, "receipt", "Record portal submission receipt",
                "Confirmation number, portal state or applicant-verified receipt", 80,
                remaining, "application")
    indexed = {r["id"]: r for r in records}
    for ref in references:
        if ref.get("status") in {"portal_verified", "declined"}:
            continue
        record = indexed.get(ref.get("application_id"))
        if record is None:
            continue
        remaining = None
        if ref.get("deadline"):
            try:
                remaining = (date.fromisoformat(ref["deadline"]) - today).days
            except ValueError:
                pass
        if remaining is not None and remaining < 0:
            continue
        add(record, "referee", "Verify referee submission in the portal",
            "Portal-generated confirmation for referee " + str(ref.get("referee_id") or "unknown"),
            74, remaining, "referees")
    conflicts = evidence_conflicts(claims)
    for conflict in conflicts:
        r = indexed.get(conflict["application_id"])
        if r is None:
            continue
        add(r, "evidence_conflict", "Resolve conflicting source claims",
            "Review and independently verify the " + conflict["field"] + " claims",
            100, None, "evidence")
    ranked = sorted(result, key=lambda item: (-item["heuristic_priority"],
                    item["application_id"], item["kind"], item["id"]))
    return {
        "as_of": today.isoformat(),
        "total": len(ranked),
        "items": ranked[:limit],
        "limit": limit,
        "method": "Rule-based proof-obligation triage, not a probability model or an evidence verification service",
        "caution": "The score is a transparent triage heuristic. It does not estimate acceptance or confirm any program requirement.",
    }
