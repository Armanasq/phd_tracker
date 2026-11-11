from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import read_settings
from .connectivity import provider_states
from .store import Store


@dataclass(frozen=True)
class ModelRoute:
    provider: dict[str, Any]
    source: str
    approved: bool


def resolve_route(store: Store, providers: list[dict[str, Any]], agent_id: str,
                  override: str | None = None) -> ModelRoute:
    preferences = read_settings(store)
    configured = preferences["agent_routes"].get(agent_id)
    if override not in (None, "", "auto"):
        identity, source = override, "request_override"
    elif configured not in (None, "", "auto"):
        identity, source = configured, "agent_assignment"
    else:
        identity, source = preferences["default_provider"], "workspace_default"
    provider = next((item for item in providers if item["id"] == identity), None)
    if provider is None:
        raise ValueError("Selected inference provider is not registered: " + str(identity))
    approved = bool(provider["local"])
    if not approved and identity in preferences["approved_cloud_providers"]:
        approved = provider_states(store, [provider])[identity]["state"] == "responded"
    return ModelRoute(provider, source, approved)


def routing_status(store: Store, providers: list[dict[str, Any]],
                   agents: list[dict[str, Any]]) -> dict[str, Any]:
    from .connectivity import provider_states

    states = provider_states(store, providers)
    preferences = read_settings(store)
    assignments = {}
    for agent in agents:
        route = resolve_route(store, providers, agent["id"])
        provider = route.provider
        assignments[agent["id"]] = {
            "provider_id": provider["id"],
            "provider_label": provider["label"],
            "model": provider["model"],
            "source": route.source,
            "state": states.get(provider["id"], {}).get("state", "needs_setup"),
            "allowed": route.approved,
        }
    active = next((p for p in providers if p["id"] == preferences["default_provider"]), None)
    return {
        "mode": "persisted_auto_route",
        "default_provider": preferences["default_provider"],
        "default_model": active["model"] if active else None,
        "default_state": states.get(preferences["default_provider"], {}).get("state", "needs_setup"),
        "agent_assignments": assignments,
        "cloud_approved": list(preferences["approved_cloud_providers"]),
        "note": "A persisted route selects a provider on future agent runs; no model inference occurs while loading settings.",
    }
