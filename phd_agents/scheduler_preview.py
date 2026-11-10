from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .connectivity import provider_states
from .engine import catalog, period_for
from .routing import resolve_route
from .route_contract import assess_provider_contract
from .settings import read_settings
from .store import Store


def scheduler_preview(store: Store, now: datetime | None = None) -> dict[str, Any]:
    config = catalog(store)
    prefs = read_settings(store)
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(prefs["timezone"]))
    providers = config["providers"]
    agent_definitions = {agent["id"]: agent for agent in config["agents"]}
    health = provider_states(store, providers)
    cloud_ids = [p["id"] for p in providers if not p["local"]]
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat(timespec="seconds")
    used = store.count_runs_since(day_start, cloud_ids)
    items = []
    for workflow in config["workflows"]:
        stages = workflow.get("steps") or [workflow["agent_id"]]
        override = workflow.get("provider_id") or "auto"
        route_steps = [resolve_route(store, providers, agent, override) for agent in stages]
        capability_checks = [
            assess_provider_contract(route.provider, agent_definitions[agent].get("requirements"))
            for agent, route in zip(stages, route_steps)
        ]
        capability_mismatch = any(not contract["compatible"] for contract in capability_checks)
        cloud_count = sum(not step.provider["local"] for step in route_steps)
        period = period_for(workflow.get("schedule", "manual"), current)
        last = store.schedule_last(workflow["id"])
        if not workflow.get("enabled"):
            state = "disabled"
        elif workflow.get("schedule") == "manual":
            state = "manual_only"
        elif period == last:
            state = "already_executed"
        elif capability_mismatch:
            state = "model_capability_mismatch"
        elif cloud_count and not workflow.get("cloud_consent"):
            state = "cloud_disclosure_not_approved"
        elif any(not step.approved for step in route_steps):
            state = "provider_not_approved"
        elif cloud_count and prefs["max_cloud_model_calls_per_day"] == 0:
            state = "cloud_budget_disabled"
        elif cloud_count and used + cloud_count > prefs["max_cloud_model_calls_per_day"]:
            state = "cloud_daily_limit"
        else:
            state = "due"
        items.append({
            "id": workflow["id"], "label": workflow["label"],
            "schedule": workflow.get("schedule", "manual"),
            "enabled": bool(workflow.get("enabled")), "state": state,
            "would_attempt": state == "due",
            "period": period or None, "last_period": last,
            "cloud_calls": cloud_count,
            "stages": [{"agent_id": agent, "provider_id": route.provider["id"],
                        "model": route.provider["model"], "source": route.source,
                        "connection_status": health[route.provider["id"]]["state"],
                        "capability_compatible": contract["compatible"],
                        "capability_blockers": contract["blockers"]}
                       for agent, route, contract in zip(stages, route_steps, capability_checks)],
        })
    return {
        "checked_at": current.isoformat(timespec="seconds"),
        "timezone": prefs["timezone"],
        "daily_cloud_call_cap": prefs["max_cloud_model_calls_per_day"],
        "recorded_daily_cloud_calls": used,
        "workflows": items,
        "due": sum(item["would_attempt"] for item in items),
        "notice": "Preview does not invoke any model or submit an application. Due means the scheduler may attempt the workflow; endpoint availability can still change.",
    }
