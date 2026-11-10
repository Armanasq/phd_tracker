from __future__ import annotations

from typing import Any


def private_runtime_capabilities(*, provider_verified: bool, provider_name: str | None = None,
                                 provider_kind: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "private_loopback",
        "security": {
            "single_owner": True,
            "loopback_only": True,
            "authenticated_cloud": False,
            "external_network_api": False,
        },
        "capabilities": {
            "public_evidence": {"supported": True, "ready": True},
            "private_state": {"supported": True, "ready": True},
            "provider_configuration": {"supported": True, "ready": True},
            "interactive_inference": {"supported": True, "ready": provider_verified},
            "agent_execution": {"supported": True, "ready": provider_verified},
            "native_streaming": {"supported": True, "ready": provider_verified and provider_kind in {"openai_compatible", "azure_openai", "azure_deployment"}, "requires": ["verified_stream_compatible_provider", "opt_in"]},
            "workflow_execution": {"supported": True, "ready": provider_verified, "requires": ["workflow_policy", "provider_approval"]},
            "background_scheduler": {"supported": True, "ready": True, "requires": ["enabled_workflow", "running_runtime"]},
            "authenticated_cloud": {"supported": False, "ready": False},
        },
        "default_provider": provider_name or None,
        "notice": "Provider readiness does not authorize cloud evidence transmission or prove university claims.",
    }
