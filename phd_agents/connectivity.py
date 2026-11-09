from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from urllib.parse import quote

from .providers import NoRedirect, ProviderError, validate_url
from .store import Store, utcnow


def credential_ready(provider: dict[str, Any]) -> bool:
    variable = str(provider.get("api_key_env") or "")
    return not variable or bool(os.environ.get(variable))


def provider_state(provider: dict[str, Any], last: dict[str, Any] | None = None) -> dict[str, Any]:
    env = str(provider.get("api_key_env") or "")
    base = str(provider.get("base_url") or "")
    model = str(provider.get("model") or "")
    reason = ""
    if "example.openai" in base or ".example/" in base or base.endswith(".example"):
        reason = "Configure your deployment endpoint"
    elif model in {"configure-me", "your-model", "model-name"}:
        reason = "Choose an installed or provisioned model"
    elif not credential_ready(provider):
        reason = "Set " + env + " in the private runtime environment"
    prior = last or {}
    state = "needs_setup" if reason else "ready_to_test"
    if not reason and prior.get("status") == "responded":
        state = "responded"
    elif not reason and prior.get("status") == "reachable":
        state = "reachable"
    elif not reason and prior.get("status") == "failed":
        state = "failed"
    return {
        "provider_id": provider["id"], "state": state, "reason": reason,
        "credential_source": "environment" if env else "none",
        "credential_configured": bool(os.environ.get(env)) if env else None,
        "last_checked": prior.get("checked_at"),
        "latency_ms": prior.get("latency_ms"),
        "model_count": prior.get("model_count"),
        "last_error": prior.get("error"),
        "last_model": prior.get("model"),
    }


def provider_states(store: Store, providers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    history = {item["id"]: item for item in store.get_custom("connection")}
    return {p["id"]: provider_state(p, history.get(p["id"])) for p in providers}


def model_list(provider: dict[str, Any], timeout: int = 12) -> dict[str, Any]:
    base = validate_url(provider["base_url"], bool(provider["local"]))
    env = str(provider.get("api_key_env") or "")
    if env and not os.environ.get(env) and not provider["local"]:
        raise ProviderError("Missing credential environment variable " + env)
    headers = {"Accept": "application/json"}
    kind = provider["kind"]
    if kind == "anthropic":
        endpoint = base + "/v1/models"
        headers["anthropic-version"] = "2023-06-01"
        if env and os.environ.get(env):
            headers["x-api-key"] = os.environ[env]
    else:
        if kind == "azure_deployment":
            version = str(provider.get("api_version") or "2024-10-21")
            endpoint = base + "/openai/models?api-version=" + quote(version, safe="")
        else:
            endpoint = base + "/models"
        if kind in {"azure_openai", "azure_deployment"}:
            if env and os.environ.get(env):
                headers["api-key"] = os.environ[env]
        elif env and os.environ.get(env):
            headers["Authorization"] = "Bearer " + os.environ[env]
    started = time.perf_counter()
    try:
        with build_opener(NoRedirect()).open(Request(endpoint, headers=headers), timeout=timeout) as response:
            raw = response.read(1_000_001)
    except HTTPError as error:
        raise ProviderError("Model catalog endpoint returned HTTP " + str(error.code)) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ProviderError("Model catalog unavailable: " + type(error).__name__) from error
    if len(raw) > 1_000_000:
        raise ProviderError("Model catalog exceeded size limit")
    try:
        payload = json.loads(raw)
        values = payload.get("data")
        if not isinstance(values, list):
            raise ValueError("No data array")
        models = []
        for item in values[:100]:
            if not isinstance(item, dict):
                continue
            identity = item.get("id")
            if isinstance(identity, str) and identity and len(identity) <= 160:
                models.append({"id": identity, "name": str(item.get("display_name") or item.get("name") or identity)[:160]})
        return {"status": "reachable", "provider_id": provider["id"], "models": models,
                "model_count": len(models), "latency_ms": round((time.perf_counter() - started) * 1000),
                "limited_to": 100, "note": "Catalog availability does not guarantee inference permission for a model"}
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ProviderError("Provider model catalog response is incompatible") from error


def remember_check(store: Store, provider_id: str, *, status: str, model: str = "",
                   latency_ms: int | None = None, model_count: int | None = None,
                   error: str = "") -> None:
    store.put_custom("connection", {
        "id": provider_id, "status": status, "model": model[:160], "latency_ms": latency_ms,
        "model_count": model_count, "error": error[:180], "checked_at": utcnow()
    })
