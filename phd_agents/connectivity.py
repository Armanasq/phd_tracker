from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from .secrets import read_secret
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from urllib.parse import quote

from .providers import NoRedirect, ProviderError, validate_url, validate_credential_binding
from .egress import PinnedHTTPHandler, PinnedHTTPSHandler
from .catalog import PROVIDERS
from .store import Store, utcnow


def credential_fingerprint(provider: dict[str, Any]) -> str:
    env = str(provider.get("api_key_env") or "")
    secret = read_secret(env) if env else ""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest() if secret else ""


def connection_fresh(checked_at: object, *, now: datetime | None = None) -> bool:
    if not isinstance(checked_at, str):
        return False
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if checked.tzinfo is None:
        return False
    age = ((now or datetime.now(timezone.utc)) - checked.astimezone(timezone.utc)).total_seconds()
    return -300 <= age <= 86_400


def credential_ready(provider: dict[str, Any]) -> bool:
    variable = str(provider.get("api_key_env") or "")
    return not variable or bool(read_secret(variable))


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
        reason = "Configure a credential for " + env + " in private Settings"
    prior = last or {}
    state = "needs_setup" if reason else "ready_to_test"
    previous = prior.get("status")
    if not reason and previous in {"responded", "reachable"}:
        previous_fingerprint = prior.get("credential_fingerprint")
        current_fingerprint = credential_fingerprint(provider)
        if env and (not isinstance(previous_fingerprint, str) or previous_fingerprint != current_fingerprint):
            state = "needs_reverification"
            reason = "Provider credential has changed or was never fingerprinted; test the connection"
        elif not connection_fresh(prior.get("checked_at")):
            state = "stale"
            reason = "Provider check is older than 24 hours; test again"
        else:
            state = previous
    elif not reason and previous == "failed":
        state = "failed"
    return {
        "provider_id": provider["id"], "state": state, "reason": reason,
        "credential_source": ("environment" if env and os.environ.get(env) else "private_store" if env and read_secret(env) else "none"),
        "credential_configured": bool(read_secret(env)) if env else None,
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
    validate_credential_binding(provider)
    env = str(provider.get("api_key_env") or "")
    api_key = read_secret(env) if env else ""
    if env and not api_key and not provider["local"]:
        raise ProviderError("Missing private credential " + env)
    headers = {"Accept": "application/json"}
    kind = provider["kind"]
    if kind == "anthropic":
        endpoint = base + "/v1/models"
        headers["anthropic-version"] = "2023-06-01"
        if api_key:
            headers["x-api-key"] = api_key
    else:
        if kind == "azure_deployment":
            version = str(provider.get("api_version") or "2024-10-21")
            endpoint = base + "/openai/models?api-version=" + quote(version, safe="")
        else:
            endpoint = base + "/models"
        if kind in {"azure_openai", "azure_deployment"}:
            if api_key:
                headers["api-key"] = api_key
        elif api_key:
            headers["Authorization"] = "Bearer " + api_key
    started = time.perf_counter()
    try:
        with build_opener(NoRedirect(), ProxyHandler({}),
                          PinnedHTTPHandler(local=bool(provider["local"])),
                          PinnedHTTPSHandler(local=bool(provider["local"]))).open(
                              Request(endpoint, headers=headers), timeout=timeout) as response:
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
    provider = next((p for p in store.catalog("provider", PROVIDERS) if p["id"] == provider_id), None)
    if provider is None:
        raise ValueError("Unknown provider for connection check")
    store.put_custom("connection", {
        "id": provider_id, "status": status, "model": model[:160], "latency_ms": latency_ms,
        "model_count": model_count, "error": error[:180], "checked_at": utcnow(),
        "credential_fingerprint": credential_fingerprint(provider),
    })
