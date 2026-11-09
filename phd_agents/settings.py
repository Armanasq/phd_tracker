from __future__ import annotations

from typing import Any

from .catalog import AGENTS, PROVIDERS
from .store import Store

DEFAULTS: dict[str, Any] = {
    "default_provider": "ollama",
    "default_agent": "portfolio_planner",
    "timezone": "Europe/London",
    "max_runs_per_tick": 3,
    "max_cloud_model_calls_per_day": 0,
    "agent_routes": {},
    "approved_cloud_providers": [],
    "confirm_cloud_each_run": True,
}

def read_settings(store: Store) -> dict[str, Any]:
    values = store.get_custom("setting")
    stored = next((item for item in values if item.get("id") == "preferences"), {})
    return {**DEFAULTS, **{k: stored[k] for k in DEFAULTS if k in stored}}

def save_settings(store: Store, changes: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes or set(changes) - set(DEFAULTS):
        raise ValueError("Unsupported settings fields")
    settings = {**read_settings(store), **changes}
    providers = {x["id"] for x in store.catalog("provider", PROVIDERS)}
    agents = {x["id"] for x in store.catalog("agent", AGENTS)}
    if settings["default_provider"] not in providers or settings["default_agent"] not in agents:
        raise ValueError("Default model and agent must exist in the catalog")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(settings["timezone"])
    except (ZoneInfoNotFoundError, KeyError, TypeError):
        raise ValueError("Enter a valid IANA timezone") from None
    limit = settings["max_runs_per_tick"]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 10:
        raise ValueError("Scheduled-run limit must be an integer between 1 and 10")
    cap = settings["max_cloud_model_calls_per_day"]
    if not isinstance(cap, int) or isinstance(cap, bool) or not 0 <= cap <= 100:
        raise ValueError("Daily scheduled cloud-model call cap must be in [0,100]")
    routes = settings["agent_routes"]
    if not isinstance(routes, dict) or len(routes) > 60 or any(
        agent not in agents or value not in providers for agent, value in routes.items()
    ):
        raise ValueError("Agent routing must reference registered agents and model providers")
    approvals = settings["approved_cloud_providers"]
    if not isinstance(approvals, list) or len(approvals) > 40 or len(approvals) != len(set(approvals)):
        raise ValueError("Approved cloud providers must be a unique list of provider IDs")
    cloud = {p["id"] for p in store.catalog("provider", PROVIDERS) if not p["local"]}
    if any(identity not in cloud for identity in approvals):
        raise ValueError("Cloud approval can only refer to a registered cloud provider")
    previous = set(read_settings(store)["approved_cloud_providers"])
    newly_approved = set(approvals) - previous
    if newly_approved:
        from .connectivity import provider_states
        state = provider_states(store, store.catalog("provider", PROVIDERS))
        if any(state[identity]["state"] != "responded" for identity in newly_approved):
            raise ValueError("Verify cloud model inference successfully before enabling automatic use")
    if settings["confirm_cloud_each_run"] is not True:
        raise ValueError("Manual cloud disclosure approval cannot be disabled")
    store.put_custom("setting", {"id": "preferences", **settings})
    return settings
