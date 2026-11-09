from __future__ import annotations

from datetime import date
from typing import Any

from .domain import agenda, plan_capacity, preflight
from .operations import evidence_conflicts, milestones_for, referee_matrix, research_fit_signals

TOOL_NAMES = frozenset({"preflight", "daily_agenda", "deadline_clocks", "referee_dependencies",
                        "evidence_disputes", "research_alignment", "capacity_screen", "discovery_health"})
DEFAULT_TOOLS = {
    "portfolio_planner": ["daily_agenda", "capacity_screen", "discovery_health"],
    "deadline_auditor": ["deadline_clocks", "evidence_disputes"],
    "eligibility_auditor": ["preflight", "evidence_disputes"],
    "research_fit": ["research_alignment", "discovery_health"],
    "faculty_outreach": ["research_alignment", "preflight"],
    "referee_coordinator": ["referee_dependencies", "deadline_clocks"],
    "document_reviewer": ["preflight", "daily_agenda"],
    "submission_preflight": ["preflight", "deadline_clocks", "referee_dependencies"],
    "inbox_triage": ["evidence_disputes", "deadline_clocks"],
    "interview_coach": ["research_alignment"],
    "research_gap": ["research_alignment", "discovery_health"],
    "funding_analyst": ["preflight", "evidence_disputes"],
}

def run_tools(names: list[str], *, data: dict[str, Any], records: list[dict[str, Any]],
              private: dict[str, list[dict[str, Any]]], today: date,
              application_id: str | None = None) -> dict[str, Any]:
    if len(names) > 8 or any(name not in TOOL_NAMES for name in names):
        raise ValueError("Tool invocation exceeds the allowlist or budget")
    relevant = [r for r in records if r.get("id") == application_id] if application_id else records
    profile = (private.get("profile") or [{}])[0]
    reports = []
    for name in dict.fromkeys(names):
        if name == "preflight":
            chosen = relevant[:15]
            result = [preflight(r, today) for r in chosen]
        elif name == "daily_agenda":
            result = agenda(relevant, today, 20)
        elif name == "deadline_clocks":
            result = milestones_for(relevant, private.get("milestone", []), today)[:35]
        elif name == "referee_dependencies":
            refs = private.get("reference", [])
            if application_id:
                refs = [x for x in refs if x.get("application_id") == application_id]
            result = referee_matrix(private.get("referee", []), refs, today)
            result["requests"] = result["requests"][:35]
        elif name == "evidence_disputes":
            claims = private.get("evidence", [])
            if application_id:
                claims = [x for x in claims if x.get("application_id") == application_id]
            result = evidence_conflicts(claims)[:35]
        elif name == "research_alignment":
            result = research_fit_signals(profile, relevant)[:20]
        elif name == "capacity_screen":
            hours = profile.get("hours_per_week")
            result = plan_capacity(relevant, today, hours)
        elif name == "discovery_health":
            result = data.get("providers", [])
        else:
            raise ValueError("Unsupported tool")
        reports.append({"name": name, "status": "completed", "result": result})
    return {"tools": reports, "count": len(reports), "side_effects": "none"}
