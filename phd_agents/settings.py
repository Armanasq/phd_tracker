from __future__ import annotations

from typing import Any

from .catalog import AGENTS, PROVIDERS
from .store import Store

DEFAULTS: dict[str, Any] = {
    "default_provider": "ollama",
    "default_agent": "portfolio_planner",
    "timezone": "Europe/London",
    "max_runs_per_tick": 3,
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
    if settings["confirm_cloud_each_run"] is not True:
        raise ValueError("Manual cloud disclosure approval cannot be disabled")
    store.put_custom("setting", {"id": "preferences", **settings})
    return settings
