from __future__ import annotations

from typing import Any

_REQUIREMENT_FLAGS = frozenset({
    "requires_native_tools", "requires_structured_output", "requires_vision",
})
_STREAM_ADAPTERS = frozenset({"openai_compatible", "azure_openai", "azure_deployment"})


def normalize_requirements(value: object = None) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - (_REQUIREMENT_FLAGS | {"min_output_tokens"}):
        raise ValueError("Unsupported agent capability requirements")
    tokens = value.get("min_output_tokens", 64)
    if type(tokens) is not int or not 64 <= tokens <= 16384:
        raise ValueError("Agent minimum output tokens must be an integer in [64,16384]")
    flags = {}
    for name in sorted(_REQUIREMENT_FLAGS):
        flag = value.get(name, False)
        if type(flag) is not bool:
            raise ValueError("Agent capability flags must be booleans")
        flags[name] = flag
    return {"schema_version": 1, "min_output_tokens": tokens, **flags}


def adapter_capabilities(provider: dict[str, Any]) -> dict[str, Any]:
    kind = provider.get("kind")
    if kind not in _STREAM_ADAPTERS | {"anthropic"}:
        raise ValueError("Unrecognized provider adapter kind")
    return {
        "schema_version": 1,
        "text_input": True,
        "native_sse_adapter": kind in _STREAM_ADAPTERS,
        "native_tool_calling": False,
        "json_schema_output": False,
        "vision_input": False,
        "status": "adapter_implementation_only_not_a_live_model_probe",
    }


def assess_provider_contract(
    provider: dict[str, Any], requirements: object = None,
    *, stream_requested: bool = False,
) -> dict[str, Any]:
    if type(stream_requested) is not bool:
        raise ValueError("Streaming requirement must be boolean")
    needed = normalize_requirements(requirements)
    available = adapter_capabilities(provider)
    limit = provider.get("max_output_tokens")
    if type(limit) is not int or not 64 <= limit <= 16384:
        raise ValueError("Provider output limit is missing or invalid")
    blockers = []
    if limit < needed["min_output_tokens"]:
        blockers.append("output_token_limit_below_agent_minimum")
    if needed["requires_native_tools"] and not available["native_tool_calling"]:
        blockers.append("native_tool_calling_not_implemented")
    if needed["requires_structured_output"] and not available["json_schema_output"]:
        blockers.append("validated_json_schema_output_not_implemented")
    if needed["requires_vision"] and not available["vision_input"]:
        blockers.append("vision_input_not_implemented")
    if stream_requested and not available["native_sse_adapter"]:
        blockers.append("native_sse_not_supported_by_adapter")
    return {
        "schema_version": 1,
        "provider_id": str(provider.get("id") or "")[:64],
        "requirements": needed,
        "adapter": available,
        "compatible": not blockers,
        "blockers": blockers,
    }
