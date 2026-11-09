from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

def snapshot(root: Path) -> dict[str, Any]:
    from scripts.build_workspace import build
    return build(root)

def today_in(zone: str = "Europe/London") -> date:
    return datetime.now(ZoneInfo(zone)).date()

def merged_records(data: dict[str, Any], overlays: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged = []
    for record in data["records"]:
        owner = overlays.get(record["id"], {})
        combined = dict(record)
        for key in ("status", "contact_status", "followup", "priority", "next_step", "notes", "receipt", "estimated_hours", "referees", "evidence_flags"):
            if key in owner:
                combined[key] = owner[key]
        combined["document_states"] = {**record.get("document_states", {}), **owner.get("document_states", {})}
        combined["private_version"] = owner.get("version", 0)
        merged.append(combined)
    return merged

def days_left(record: dict[str, Any], today: date) -> int | None:
    try:
        return (date.fromisoformat(record["deadline"]) - today).days
    except (ValueError, TypeError, KeyError):
        return None

def preflight(record: dict[str, Any], today: date) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    def add(code: str, status: str, explanation: str):
        checks.append({"code": code, "status": status, "explanation": explanation})
    if record.get("record_type") != "tracked":
        add("tracked", "blocker", "Research candidates must be source-reviewed and promoted first")
    else:
        add("tracked", "pass", "Registered application record")
    if record.get("status") == "submitted":
        add("submission", "pass" if record.get("receipt") else "unknown", "Owner marked submitted; verify portal receipt independently")
    elif record.get("status") in {"blocked", "rejected", "withdrawn", "archived", "offer"}:
        add("application_state", "blocker", "Record is not in the preparation pipeline")
    delta = days_left(record, today)
    if delta is None:
        add("deadline", "unknown", "Official final cutoff date is missing")
    elif delta < 0:
        add("deadline", "blocker", "Recorded deadline has passed; confirm whether reopened before acting")
    else:
        add("deadline", "pass", f"Recorded calendar date is {delta} day(s) away")
    if record.get("deadline_type") != "final":
        add("deadline_kind", "unknown", "Recorded date is not independently classified as final")
    if record.get("deadline") and not record.get("deadline_time_verified"):
        add("cutoff_time", "unknown", "Exact cutoff time and IANA time zone are unverified")
    if record.get("verification") not in {"source_verified", "owner_verified"}:
        add("primary_source", "unknown", "Official source has not passed an explicit verification gate")
    else:
        add("primary_source", "pass", "Source review recorded; recheck the live portal before submitting")
    if not record.get("apply_url"):
        add("application_route", "unknown", "Official submission route not recorded")
    if record.get("duplicate_submission_advisory"):
        add("duplicate_route", "blocker", "Possible shared/duplicate submission pathway requires manual resolution")
    if not record.get("funding") or not record.get("eligibility"):
        add("funding_eligibility", "unknown", "Personal funding eligibility has not been independently established")
    docs = record.get("documents", [])
    if not docs:
        add("requirements", "unknown", "Document requirements need official verification")
    for doc in docs:
        state = record.get("document_states", {}).get(doc, "unknown")
        add("document:" + doc, "pass" if state in {"ready", "not_applicable"} else "blocker" if state == "not_started" else "unknown",
            "Document state: " + state)
    counts = dict(Counter(x["status"] for x in checks))
    return {"application_id": record["id"], "checks": checks, "counts": counts,
            "ready": counts.get("blocker", 0) == 0 and counts.get("unknown", 0) == 0,
            "policy": "Checklists do not establish submission or personal eligibility. The applicant must verify the final portal."}

def agenda(records: list[dict[str, Any]], today: date, limit: int = 40) -> list[dict[str, Any]]:
    tasks = []
    reuse: Counter[str] = Counter(d for r in records if r["record_type"] == "tracked" for d in r.get("documents", []))
    for r in records:
        if r.get("record_type") != "tracked" or r.get("status") in {"rejected", "withdrawn", "archived", "blocked", "offer"}:
            continue
        due = days_left(r, today)
        if r.get("status") == "submitted":
            followup = r.get("followup")
            try:
                days = (date.fromisoformat(followup) - today).days
                if days <= 14:
                    tasks.append({"application_id": r["id"], "kind": "post_submission", "label": "Review submission follow-up / referee status", "days": days,
                                  "priority": 85 if days <= 0 else 35, "evidence": "Owner-controlled follow-up date"})
            except (ValueError, TypeError):
                pass
            continue
        if due is not None and due < 0:
            continue
        urgency = 95 if due == 0 else 75 if due is not None and due <= 3 else 55 if due is not None and due <= 7 else 25
        if r.get("verification") not in {"source_verified", "owner_verified"}:
            tasks.append({"application_id": r["id"], "kind": "verify", "label": "Verify official application source and eligibility",
                          "days": due, "priority": urgency + 5, "evidence": r.get("source_url") or "Primary source missing"})
        else:
            tasks.append({"application_id": r["id"], "kind": "prepare", "label": r.get("next_step") or "Review remaining application requirements",
                          "days": due, "priority": urgency, "evidence": r.get("source_url") or "Check official portal"})
        for doc in r.get("documents", []):
            state = r.get("document_states", {}).get(doc, "unknown")
            if state != "ready" and state != "not_applicable":
                tasks.append({"application_id": r["id"], "kind": "document", "resource": doc,
                              "label": ("Confirm readiness" if state == "unknown" else "Prepare") + ": " + doc.replace("_", " "),
                              "days": due, "priority": urgency + min(20, reuse[doc] // 3),
                              "evidence": "Applicant readiness is " + state})
        if r.get("duplicate_submission_advisory"):
            tasks.append({"application_id": r["id"], "kind": "route_conflict", "label": "Resolve duplicate submission route",
                          "days": due, "priority": urgency + 15, "evidence": "Source notes flag a multi-route caution"})
    tasks.sort(key=lambda x: (-x["priority"], x["days"] if x["days"] is not None else 9999, x["application_id"]))
    return tasks[:max(1, min(int(limit), 200))]

def plan_capacity(records: list[dict[str, Any]], today: date, hours_per_week: float | None) -> dict[str, Any]:
    if hours_per_week is None:
        return {"status": "needs_capacity", "explanation": "Enter available hours per week before claiming feasibility", "scheduled": [], "unknown_effort": []}
    if not 0 < hours_per_week <= 168:
        raise ValueError("Weekly capacity must be in (0,168]")
    candidates = [r for r in records if r.get("record_type") == "tracked" and r.get("status") not in {"submitted", "rejected", "withdrawn", "archived", "blocked", "offer"} and (days_left(r, today) is None or days_left(r, today) >= 0)]
    candidates.sort(key=lambda r: (days_left(r, today) if days_left(r, today) is not None else 9999, r["id"]))
    scheduled = []
    unknown_effort = []
    for r in candidates:
        estimate = r.get("estimated_hours")
        if not isinstance(estimate, (int, float)) or estimate <= 0:
            unknown_effort.append(r["id"])
            continue
        days = days_left(r, today)
        capacity = (hours_per_week * max(1, days if days is not None else 7) / 7)
        scheduled.append({"application_id": r["id"], "estimated_hours": estimate, "available_hours_until_deadline": round(capacity, 1),
                          "individually_feasible": estimate <= capacity,
                          "caveat": "Individual upper bound; shared capacity and dependencies are not jointly optimized"})
    return {"status": "provisional", "scheduled": scheduled, "unknown_effort": unknown_effort,
            "explanation": "Estimates are owner-entered. This is a screening bound, not a full resource-constrained schedule."}
