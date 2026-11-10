from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KINDS = {"referee", "reference", "milestone", "evidence", "profile"}
REF_STATES = {"not_requested", "requested", "acknowledged", "uploaded", "portal_verified", "declined"}
MILESTONE_TYPES = {"final", "priority", "scholarship", "referee", "supervisor_contact", "interview", "offer", "registration", "other"}
EVIDENCE_STATUSES = {"unverified", "primary_confirmed", "needs_review", "contradicted", "superseded"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.-]{1,100}$")

def normalize_item(kind: str, value: dict[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("Unsupported private record type")
    if not isinstance(value, dict):
        raise ValueError("Private record must be an object")
    if kind == "profile":
        identity = "applicant"
        value = {"id": identity, **value}
        value["id"] = identity
    else:
        identity = str(value.get("id") or "")
        if not SAFE_ID.fullmatch(identity):
            raise ValueError("Record ID must contain 2–100 safe characters")
    allowed = {
        "referee": {"id", "name", "contact", "affiliation", "notes"},
        "reference": {"id", "referee_id", "application_id", "status", "deadline", "requested_at", "acknowledged_at", "uploaded_at", "portal_verified_at", "notes"},
        "milestone": {"id", "application_id", "kind", "date", "time", "timezone", "source_url", "verification", "notes"},
        "evidence": {"id", "application_id", "field", "assertion", "source_url", "observed_at", "status", "excerpt", "notes"},
        "profile": {"id", "research_topics", "skills", "projects", "hours_per_week", "document_effort", "notes"}
    }[kind]
    if set(value) - allowed:
        raise ValueError("Unrecognized private " + kind + " fields")
    candidate = dict(value)
    candidate["id"] = identity
    for field in ("name", "contact", "affiliation", "notes", "field", "assertion", "excerpt", "source_url", "referee_id", "application_id", "timezone"):
        if field in candidate and (not isinstance(candidate[field], str) or len(candidate[field]) > (3000 if field in {"notes", "assertion", "excerpt"} else 500)):
            raise ValueError("Invalid field: " + field)
    if kind == "referee" and not candidate.get("name"):
        raise ValueError("Referee name is required")
    if kind == "reference":
        if not candidate.get("referee_id") or not candidate.get("application_id"):
            raise ValueError("Reference must identify referee and application")
        if candidate.get("status", "not_requested") not in REF_STATES:
            raise ValueError("Invalid reference state")
        candidate.setdefault("status", "not_requested")
    if kind == "milestone":
        if not candidate.get("application_id"):
            raise ValueError("Milestone must belong to an application")
        if candidate.get("kind") not in MILESTONE_TYPES:
            raise ValueError("Unknown milestone type")
        if candidate.get("verification", "unverified") not in EVIDENCE_STATUSES:
            raise ValueError("Invalid verification state")
        if candidate.get("time"):
            try:
                time.fromisoformat(candidate["time"])
            except (ValueError, TypeError) as error:
                raise ValueError("Invalid cutoff time") from error
            if not candidate.get("timezone"):
                raise ValueError("Exact cutoff time requires IANA timezone")
            try:
                ZoneInfo(candidate["timezone"])
            except ZoneInfoNotFoundError as error:
                raise ValueError("Unknown IANA timezone") from error
    if kind == "evidence":
        if not candidate.get("application_id") or not candidate.get("field") or not candidate.get("assertion"):
            raise ValueError("Evidence must have an application, field and assertion")
        if candidate.get("status", "unverified") not in EVIDENCE_STATUSES:
            raise ValueError("Invalid evidence status")
        candidate.setdefault("status", "unverified")
    for field in ("date", "deadline", "requested_at", "acknowledged_at", "uploaded_at", "portal_verified_at", "observed_at"):
        if candidate.get(field):
            try:
                date.fromisoformat(candidate[field][:10])
            except (ValueError, TypeError) as error:
                raise ValueError("Invalid ISO date: " + field) from error
    for field in ("source_url",):
        if candidate.get(field):
            url = urlsplit(candidate[field])
            if url.scheme != "https" or not url.netloc or url.username or url.password:
                raise ValueError("Evidence source must be HTTPS")
    if kind == "profile":
        for field in ("research_topics", "skills", "projects"):
            data = candidate.get(field, [])
            if not isinstance(data, list) or len(data) > 100 or any(not isinstance(x, str) or len(x) > 200 for x in data):
                raise ValueError("Profile " + field + " must be a short string list")
        if "hours_per_week" in candidate and candidate["hours_per_week"] is not None:
            hours = candidate["hours_per_week"]
            if isinstance(hours, bool) or not isinstance(hours, (float, int)) or not 0 < hours <= 168:
                raise ValueError("Available hours must be in (0,168]")
        effort = candidate.get("document_effort", {})
        if not isinstance(effort, dict) or len(effort) > 40 or any(not isinstance(v, (int, float)) or v < 0 or v > 300 for v in effort.values()):
            raise ValueError("Document effort must be non-negative hour estimates")
    return candidate

def milestones_for(records: list[dict[str, Any]], items: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    visible = {r["id"] for r in records}
    events = []
    for r in records:
        if r.get("record_type") == "tracked" and r.get("deadline"):
            events.append({"id": "source:" + r["id"], "application_id": r["id"], "kind": r.get("deadline_type") or "unknown",
                           "date": r["deadline"], "time": None, "timezone": None, "verification": r.get("verification"),
                           "source_url": r.get("source_url"), "provenance": "Original source snapshot"})
    for m in items:
        if m.get("application_id") in visible:
            events.append({**m, "provenance": "Private owner-maintained milestone"})
    for event in events:
        try:
            event["days_left"] = (date.fromisoformat(event["date"]) - as_of).days
        except (TypeError, ValueError, KeyError):
            event["days_left"] = None
        event["cutoff_fully_verified"] = bool(event.get("time") and event.get("timezone") and event.get("verification") == "primary_confirmed")
    return sorted(events, key=lambda x: (x["date"] if x.get("date") else "9999", x["application_id"], x["id"]))

def referee_matrix(referees: list[dict[str, Any]], references: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    people = {r["id"]: r for r in referees}
    rows = []
    for ref in references:
        due = None
        if ref.get("deadline"):
            due = (date.fromisoformat(ref["deadline"]) - as_of).days
        state = ref.get("status", "not_requested")
        rows.append({"id": ref["id"], "referee_id": ref["referee_id"],
                     "referee": people.get(ref["referee_id"], {}).get("name", "Unknown referee"),
                     "application_id": ref["application_id"], "status": state, "deadline": ref.get("deadline"),
                     "days_left": due, "needs_attention": state not in {"portal_verified", "declined"} and due is not None and due <= 7,
                     "is_portal_verified": state == "portal_verified"})
    by_referee: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_referee[row["referee_id"]].append(row["application_id"])
    return {"requests": sorted(rows, key=lambda x: (x["days_left"] if x["days_left"] is not None else 9999, x["id"])),
            "referees": len(people), "pending": sum(not r["is_portal_verified"] for r in rows),
            "urgent": sum(r["needs_attention"] for r in rows),
            "shared_dependency": {k: len(set(v)) for k, v in by_referee.items() if len(set(v)) > 1}}

def evidence_conflicts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in claims:
        if c.get("status") not in {"superseded"}:
            groups[(c.get("application_id", ""), c.get("field", ""))].append(c)
    disputes = []
    for (app_id, field), group in groups.items():
        distinct = {c.get("assertion", "").strip().casefold() for c in group}
        if len(distinct) > 1 or any(c.get("status") == "contradicted" for c in group):
            disputes.append({"application_id": app_id, "field": field, "claim_ids": [c["id"] for c in group],
                             "status": "needs_manual_resolution", "explanation": "Distinct source assertions must be reviewed, never silently reconciled"})
    return disputes

def research_fit_signals(profile: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = {str(x).casefold().strip() for field in ("research_topics", "skills") for x in profile.get(field, []) if len(str(x).strip()) >= 3}
    if not terms:
        return []
    result = []
    for record in records:
        text = " ".join(str(record.get(k) or "") for k in ("name", "topic", "fit", "next_step")).casefold()
        matches = sorted(term for term in terms if term in text)
        if matches:
            result.append({"application_id": record["id"], "matched_terms": matches,
                           "matched_count": len(matches), "interpretation": "Lexical overlap only; no hiring or acceptance inference"})
    return sorted(result, key=lambda x: (-x["matched_count"], x["application_id"]))[:80]

def resource_schedule(records: list[dict[str, Any]], as_of: date, hours_per_week: float, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    from .capacity import joint_capacity_schedule
    return joint_capacity_schedule(records, as_of, hours_per_week, profile)
