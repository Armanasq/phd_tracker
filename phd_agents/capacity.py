from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

CLOSED = frozenset({"submitted", "offer", "rejected", "withdrawn", "archived", "blocked"})
DOCUMENTS = frozenset({"academic_cv", "research_statement", "transcripts", "recommendations", "english_proof", "research_portfolio"})
DONE = frozenset({"ready", "not_applicable"})
MAX_DAYS = 365
MAX_RECORDS = 500
MAX_BLOCKS = 1200
EPS = 1e-7


def _hours(value: object, maximum: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0 < number <= maximum else None


def _date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except ValueError:
        return None


def _bottlenecks(jobs: list[dict[str, Any]], today: date, daily: float) -> list[dict[str, Any]]:
    by_date: dict[date, float] = {}
    for item in jobs:
        by_date[item["due"]] = by_date.get(item["due"], 0.0) + item["hours"]
    cumulative = 0.0
    output = []
    for due in sorted(by_date):
        cumulative += by_date[due]
        capacity = ((due - today).days + 1) * daily
        if cumulative > capacity + EPS:
            output.append({
                "deadline": due.isoformat(), "due_work_hours": round(cumulative, 2),
                "available_hours": round(capacity, 2),
                "minimum_shortfall_hours": round(cumulative - capacity, 2),
            })
    return output


def _allocate(jobs: list[dict[str, Any]], today: date, daily: float) -> dict[str, Any]:
    ordered = sorted(jobs, key=lambda row: (row["due"], row["type"] != "document", row["priority"] != "high", row["id"]))
    remaining = {row["id"]: row["hours"] for row in ordered}
    last = max((row["due"] for row in ordered), default=today)
    allocations = []
    allocation_count = 0
    allocated = 0.0
    for offset in range((last - today).days + 1):
        current = today + timedelta(days=offset)
        available = daily
        for row in ordered:
            if row["due"] < current:
                continue
            amount = min(available, remaining[row["id"]])
            if amount <= EPS:
                continue
            available -= amount
            allocated += amount
            remaining[row["id"]] -= amount
            allocation_count += 1
            if len(allocations) < MAX_BLOCKS:
                allocations.append({
                    "date": current.isoformat(), "task_id": row["id"],
                    "task_type": row["type"],
                    "application_id": row.get("application_id"), "hours": round(amount, 3),
                })
            if available <= EPS:
                break
    undone = [
        {
            "task_id": row["id"], "task_type": row["type"],
            "application_id": row.get("application_id"),
            "deadline": row["due"].isoformat(),
            "hours_unallocated": round(max(0, remaining[row["id"]]), 2),
        }
        for row in ordered if remaining[row["id"]] > EPS
    ]
    return {
        "scheduled": allocations, "total_allocations": allocation_count,
        "allocations_truncated": allocation_count > MAX_BLOCKS,
        "unallocated": undone,
        "total_work_hours": round(sum(row["hours"] for row in ordered), 2),
        "total_hours_allocated": round(allocated, 2),
        "total_hours_unallocated": round(sum(remaining.values()), 2),
        "deadline_bottlenecks": _bottlenecks(ordered, today, daily),
    }


def joint_capacity_schedule(
    records: list[dict[str, Any]], today: date, hours_per_week: float,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(today, date) or isinstance(today, datetime):
        raise ValueError("Observation date must be a date")
    weekly = _hours(hours_per_week, 168)
    if weekly is None:
        raise ValueError("Available hours must be a finite number in (0,168]")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("Capacity planner accepts up to 500 application records")
    document_effort = (profile or {}).get("document_effort", {})
    if not isinstance(document_effort, dict) or any(
        k not in DOCUMENTS or isinstance(v, bool) or not isinstance(v, (int, float))
        or not math.isfinite(float(v)) or not 0 <= v <= 300
        for k, v in document_effort.items()
    ):
        raise ValueError("Shared document estimates must be finite nonnegative hours for supported document types")
    apps = []
    unknown = []
    requirements_unrecorded = []
    documents: dict[str, dict[str, Any]] = {}
    ids: set[str] = set()
    horizon = today + timedelta(days=MAX_DAYS)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Application records must be objects")
        if row.get("record_type") != "tracked" or row.get("status") in CLOSED:
            continue
        rid = row.get("id")
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError("Application IDs must be unique nonempty strings")
        ids.add(rid)
        due = _date(row.get("deadline"))
        if due is None:
            unknown.append({"application_id": rid, "reason": "Deadline unavailable or invalid"})
            continue
        if due < today:
            continue
        if due > horizon:
            unknown.append({"application_id": rid, "reason": "Deadline beyond 365-day planning horizon"})
            continue
        estimate = _hours(row.get("estimated_hours"), 400)
        if estimate is None:
            unknown.append({"application_id": rid, "reason": "Estimated remaining application work required"})
        else:
            apps.append({
                "id": "application:" + rid, "application_id": rid, "type": "application",
                "hours": estimate, "due": due, "priority": row.get("priority"),
            })
        requirements = row.get("documents")
        if not isinstance(requirements, list) or not requirements:
            requirements_unrecorded.append(rid)
            continue
        states = row.get("document_states", {})
        if not isinstance(states, dict):
            states = {}
        for key in requirements:
            if key not in DOCUMENTS or states.get(key) in DONE:
                continue
            existing = documents.get(key)
            if existing is None:
                documents[key] = {"key": key, "due": due, "applications": {rid}}
            else:
                existing["due"] = min(existing["due"], due)
                existing["applications"].add(rid)
    extra = []
    unknown_docs = []
    for key, detail in sorted(documents.items()):
        estimate = float(document_effort[key]) if key in document_effort else None
        if estimate is None:
            unknown_docs.append({
                "document": key, "applications": len(detail["applications"]),
                "reason": "Shared preparation effort unestimated; readiness may also be unknown",
            })
        elif estimate > 0:
            extra.append({
                "id": "document:" + key, "application_id": None, "type": "document",
                "due": detail["due"], "hours": estimate, "priority": "high",
            })
    daily = weekly / 7
    base = _allocate(apps, today, daily)
    additive = _allocate(apps + extra, today, daily)
    return {
        "method": "earliest recorded deadline first under shared daily capacity; heuristic, not optimal",
        "available_hours_per_week": weekly,
        "assumed_daily_hours": round(daily, 3),
        "planning_horizon_days": MAX_DAYS,
        "scenario": "application_plus_one_shared_document_task_per_known_type",
        "scheduled": additive["scheduled"],
        "allocations_truncated": additive["allocations_truncated"],
        "unallocated": additive["unallocated"],
        "unknown_effort_or_date": unknown,
        "shared_document_hours": {key: float(document_effort[key]) for key in documents if key in document_effort},
        "unknown_document_effort": unknown_docs,
        "unconfirmed_document_requirements": requirements_unrecorded,
        "baseline": {k: v for k, v in base.items() if k != "scheduled"},
        "with_shared_documents": {k: v for k, v in additive.items() if k != "scheduled"},
        "deadline_bottlenecks": additive["deadline_bottlenecks"],
        "assumptions": [
            "Weekly hours are evenly distributed across seven calendar days, including the closing date. Exact cutoff hours are unverified.",
            "Shared document effort is counted once per type and added to application estimates; some estimates may overlap.",
            "Document reuse across institutions is not presumed valid without explicit checking.",
            "Unestimated applications and document work are excluded from numerical scenarios, never counted as zero.",
            "Dependencies, holidays, availability, referee response times and per-program document customization are not optimized.",
        ],
        "status": "over_capacity" if additive["unallocated"] else "unresolved_inputs" if (unknown or unknown_docs or requirements_unrecorded) else "screened_within_assumptions",
        "caution": "No feasibility guarantee; shared-work overlap, unknown effort and official cutoff times require independent confirmation.",
    }
