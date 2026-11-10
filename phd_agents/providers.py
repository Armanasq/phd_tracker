from __future__ import annotations

import ipaddress
import json
import os
from .secrets import read_secret
from .egress import PinnedHTTPHandler, PinnedHTTPSHandler
from .streaming import StreamFormatError, sse_events
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote
from urllib.request import HTTPRedirectHandler, Request, build_opener, ProxyHandler


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelReply:
    content: str
    model: str
    usage: dict[str, int]
    provider_id: str
    latency_ms: int | None = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ProviderError("Model provider redirected its request; redirects are disabled")


def validate_url(value: object, local: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("Provider URL is required")
    candidate = value.rstrip("/")
    parts = urlsplit(candidate)
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Invalid model-provider URL")
    if parts.scheme not in {"https", "http"}:
        raise ValueError("Only HTTP(S) providers are supported")
    host = parts.hostname.casefold()
    loopback = host == "localhost"
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_loopback:
            raise ValueError("Direct non-loopback IP targets are not permitted")
        loopback = True
    except ValueError as err:
        if "not permitted" in str(err):
            raise
    if not local and (loopback or host.endswith((".local", ".internal", ".localhost"))):
        raise ValueError("Cloud providers may not target private or loopback hostnames")
    if parts.scheme == "http" and not (local and loopback):
        raise ValueError("Unencrypted model connections are permitted only on loopback")
    if local and not loopback:
        raise ValueError("Local providers must use loopback; configure a remote HTTPS self-hosted server as cloud to require disclosure consent")
    return candidate


_CREDENTIAL_HOSTS: dict[str, tuple[str, ...]] = {
    "OPENAI_API_KEY": ("api.openai.com",),
    "AZURE_OPENAI_API_KEY": (".openai.azure.com", ".cognitiveservices.azure.com"),
    "ANTHROPIC_API_KEY": ("api.anthropic.com",),
    "GEMINI_API_KEY": ("generativelanguage.googleapis.com",),
    "OPENROUTER_API_KEY": ("openrouter.ai",),
    "GROQ_API_KEY": ("api.groq.com",),
    "DEEPSEEK_API_KEY": ("api.deepseek.com",),
    "XAI_API_KEY": ("api.x.ai",),
    "TOGETHER_API_KEY": ("api.together.xyz",),
    "FIREWORKS_API_KEY": ("api.fireworks.ai",),
    "MISTRAL_API_KEY": ("api.mistral.ai",),
    "CEREBRAS_API_KEY": ("api.cerebras.ai",),
}


def validate_credential_binding(provider: dict[str, Any]) -> None:
    key_name = str(provider.get("api_key_env") or "")
    local = bool(provider.get("local"))
    base = validate_url(provider.get("base_url"), local)
    host = urlsplit(base).hostname
    if not host:
        raise ValueError("Provider endpoint hostname is required")
    if key_name == "VLLM_API_KEY" and not local:
        raise ValueError("Use a dedicated credential variable for a remote self-hosted model gateway")
    approved_hosts = _CREDENTIAL_HOSTS.get(key_name)
    if approved_hosts and not any(
        host.endswith(name) if name.startswith(".") else host == name
        for name in approved_hosts
    ):
        raise ValueError(
            "Credential " + key_name + " is restricted to its official provider host. "
            "Use a dedicated *_API_KEY variable for a custom gateway"
        )


def invoke(provider: dict[str, Any], system: str, prompt: str, *, timeout: int | None = None) -> ModelReply:
    validate_credential_binding(provider)
    key_name = provider.get("api_key_env", "")
    api_key = read_secret(key_name) if key_name else ""
    if key_name and not api_key and not provider["local"]:
        raise ProviderError("Missing provider credential in environment variable " + key_name)
    effective_timeout = int(provider.get("timeout_seconds", 55)) if timeout is None else timeout
    kind = provider["kind"]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    model = provider["model"]
    limit = int(provider["max_output_tokens"])
    base = provider["base_url"].rstrip("/")
    if kind == "anthropic":
        url = base + "/v1/messages"
        if not api_key:
            raise ProviderError("Anthropic requires the configured API key")
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        payload = {"model": model, "max_tokens": limit, "system": system,
                   "messages": [{"role": "user", "content": prompt}]}
        if "temperature" in provider:
            payload["temperature"] = provider["temperature"]
    else:
        if kind == "azure_deployment":
            version = str(provider.get("api_version") or "2024-10-21")
            url = base + "/openai/deployments/" + quote(model, safe="") + "/chat/completions?api-version=" + quote(version, safe="")
        else:
            url = base + "/chat/completions"
        if kind in {"azure_openai", "azure_deployment"}:
            if not api_key:
                raise ProviderError("Azure OpenAI requires the configured API key")
            headers["api-key"] = api_key
        elif api_key:
            headers["Authorization"] = "Bearer " + api_key
        payload = {"model": model,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": prompt}],
                   provider["token_parameter"]: limit, "stream": False}
        if "temperature" in provider:
            payload["temperature"] = provider["temperature"]
    if len(prompt) > 25000:
        raise ValueError("Prompt exceeds the configured input budget")
    request = Request(url, json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    started = perf_counter()
    opener = build_opener(NoRedirect(), ProxyHandler({}),
                          PinnedHTTPHandler(local=bool(provider["local"])),
                          PinnedHTTPSHandler(local=bool(provider["local"])))
    try:
        with opener.open(request, timeout=effective_timeout) as response:
            raw = response.read(2_000_001)
    except HTTPError as error:
        raise ProviderError(f"Model request failed: HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise ProviderError(f"Model provider unavailable ({type(error).__name__})") from error
    if len(raw) > 2_000_000:
        raise ProviderError("Model response exceeded safety limit")
    try:
        data = json.loads(raw)
        if kind == "anthropic":
            content = "\n".join(item.get("text", "") for item in data.get("content", []) if item.get("type") == "text")
        else:
            content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("No model text")
        usage = data.get("usage") or {}
        return ModelReply(content[:20000], str(data.get("model") or model),
                          {k: int(usage.get(k, 0)) for k in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens")
                           if isinstance(usage.get(k), (int, float))}, provider["id"],
                          round((perf_counter() - started) * 1000))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ProviderError("Malformed model-provider response") from error


def invoke_stream(provider: dict[str, Any], system: str, prompt: str,
                  on_delta: Callable[[str], None], *,
                  timeout: int | None = None) -> ModelReply:
    validate_credential_binding(provider)
    kind = provider["kind"]
    if kind not in {"openai_compatible", "azure_openai", "azure_deployment"}:
        raise ProviderError("Native SSE streaming is unavailable for this provider type")
    if not callable(on_delta):
        raise TypeError("Stream callback must be callable")
    if len(prompt) > 25000:
        raise ValueError("Prompt exceeds the configured input budget")
    key_name = provider.get("api_key_env", "")
    api_key = read_secret(key_name) if key_name else ""
    if key_name and not api_key and not provider["local"]:
        raise ProviderError("Missing provider credential in environment variable " + key_name)
    model = provider["model"]
    base = provider["base_url"].rstrip("/")
    if kind == "azure_deployment":
        version = str(provider.get("api_version") or "2024-10-21")
        url = base + "/openai/deployments/" + quote(model, safe="") + "/chat/completions?api-version=" + quote(version, safe="")
    else:
        url = base + "/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if kind in {"azure_openai", "azure_deployment"}:
        if not api_key:
            raise ProviderError("Azure OpenAI requires the configured API key")
        headers["api-key"] = api_key
    elif api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {"model": model, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt}],
        provider["token_parameter"]: int(provider["max_output_tokens"]), "stream": True}
    if "temperature" in provider:
        payload["temperature"] = provider["temperature"]
    request = Request(url, json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    effective_timeout = int(provider.get("timeout_seconds", 55)) if timeout is None else timeout
    opener = build_opener(NoRedirect(), ProxyHandler({}),
                          PinnedHTTPHandler(local=bool(provider["local"])),
                          PinnedHTTPSHandler(local=bool(provider["local"])))
    started = perf_counter()
    text_parts: list[str] = []
    total_chars = 0
    completed = False
    usage: dict[str, int] = {}
    reported_model = model
    try:
        with opener.open(request, timeout=effective_timeout) as response:
            if "text/event-stream" not in response.headers.get("Content-Type", "").casefold():
                raise ProviderError("Provider did not return a native SSE stream")
            for event, item in sse_events(response):
                if item == "[DONE]":
                    completed = True
                    break
                if event == "error":
                    raise ProviderError("Provider reported a streaming error")
                try:
                    data = json.loads(item)
                except (ValueError, TypeError) as error:
                    raise ProviderError("Provider returned invalid SSE data") from error
                if not isinstance(data, dict) or data.get("error"):
                    raise ProviderError("Provider returned an inference error")
                if isinstance(data.get("model"), str):
                    reported_model = data["model"][:160]
                if isinstance(data.get("usage"), dict):
                    usage = {key: value for key, value in data["usage"].items()
                             if key in {"prompt_tokens", "completion_tokens", "input_tokens", "output_tokens"}
                             and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
                choices = data.get("choices")
                if not choices:
                    continue
                if not isinstance(choices, list) or not isinstance(choices[0], dict):
                    raise ProviderError("Provider SSE choices are malformed")
                delta = choices[0].get("delta")
                if not isinstance(delta, dict):
                    raise ProviderError("Provider SSE delta is malformed")
                fragment = delta.get("content")
                if fragment is None:
                    continue
                if not isinstance(fragment, str):
                    raise ProviderError("Provider SSE text delta is malformed")
                total_chars += len(fragment)
                if total_chars > 20_000:
                    raise ProviderError("Provider SSE response exceeded the text limit")
                text_parts.append(fragment)
                on_delta(fragment)
    except HTTPError as error:
        raise ProviderError("Model request failed: HTTP " + str(error.code)) from None
    except (URLError, TimeoutError, OSError) as error:
        raise ProviderError("Model streaming unavailable (" + type(error).__name__ + ")") from error
    except StreamFormatError as error:
        raise ProviderError("Malformed or oversized provider SSE stream") from error
    if not completed or not "".join(text_parts).strip():
        raise ProviderError("Provider SSE stream terminated before a complete response")
    return ModelReply("".join(text_parts), reported_model, usage, provider["id"],
                      round((perf_counter() - started) * 1000))
