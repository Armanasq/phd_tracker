from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.catalog import PROVIDERS, provider_spec
from phd_agents.connectivity import remember_check
from phd_agents.engine import run_agent, catalog
from phd_agents.routing import resolve_route, routing_status
from phd_agents.settings import read_settings, save_settings
from phd_agents.store import Store


class AutomaticRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "private.sqlite3")
        self.addCleanup(self.store.close)
        self.providers = catalog(self.store)["providers"]

    def test_default_route_applies_without_per_run_provider_id(self):
        save_settings(self.store, {"default_provider": "vllm"})
        selected = resolve_route(self.store, self.providers, "research_fit")
        self.assertEqual(selected.provider["id"], "vllm")
        self.assertEqual(selected.source, "workspace_default")
        self.assertTrue(selected.approved)
        self.assertEqual(routing_status(self.store, self.providers, catalog(self.store)["agents"])["default_provider"], "vllm")

    def test_agent_assignment_overrides_workspace_route(self):
        save_settings(self.store, {"default_provider": "ollama",
                                   "agent_routes": {"research_fit": "vllm"}})
        route = resolve_route(self.store, self.providers, "research_fit")
        self.assertEqual(route.provider["id"], "vllm")
        self.assertEqual(route.source, "agent_assignment")
        self.assertEqual(resolve_route(self.store, self.providers, "research_fit", "ollama").source, "request_override")
        with self.assertRaises(ValueError):
            save_settings(self.store, {"agent_routes": {"unknown_agent": "vllm"}})

    def test_cloud_approval_requires_real_model_probe(self):
        with self.assertRaises(ValueError):
            save_settings(self.store, {"approved_cloud_providers": ["openai"]})
        remember_check(self.store, "openai", status="reachable", model_count=2)
        with self.assertRaises(ValueError):
            save_settings(self.store, {"approved_cloud_providers": ["openai"]})
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-only-test-key"}):
            remember_check(self.store, "openai", status="responded", model="gpt-test")
            self.assertEqual(save_settings(self.store, {"approved_cloud_providers": ["openai"]})["approved_cloud_providers"], ["openai"])
        route = resolve_route(self.store, self.providers, "portfolio_planner", "openai")
        self.assertTrue(route.approved)
        self.store.put_custom("provider", provider_spec(next(p for p in self.providers if p["id"] == "openai")))
        self.assertEqual(read_settings(self.store)["approved_cloud_providers"], [])
        self.assertFalse(resolve_route(self.store, catalog(self.store)["providers"], "portfolio_planner", "openai").approved)

    def test_custom_endpoint_uses_saved_default(self):
        self.store.put_custom("provider", provider_spec({
            "id": "my_vllm", "label": "Research local model", "kind": "openai_compatible",
            "base_url": "http://127.0.0.1:8000/v1", "local": True, "model": "my-model",
            "api_key_env": "", "token_parameter": "max_tokens"}))
        save_settings(self.store, {"default_provider": "my_vllm"})
        selected = resolve_route(self.store, catalog(self.store)["providers"], "portfolio_planner")
        self.assertEqual(selected.provider["base_url"], "http://127.0.0.1:8000/v1")
        self.assertEqual(selected.provider["model"], "my-model")


if __name__ == "__main__":
    unittest.main()
