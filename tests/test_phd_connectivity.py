from __future__ import annotations

import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.catalog import PROVIDERS
from phd_agents.connectivity import model_list, provider_state, provider_states, remember_check
from phd_agents.providers import validate_url
from phd_agents.server import ApiServer
from phd_agents.settings import DEFAULTS, read_settings, save_settings
from phd_agents.store import Store


class SettingsAndConnectivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "app.sqlite3")
        self.addCleanup(self.store.close)

    def test_settings_are_private_and_validated(self) -> None:
        self.assertEqual(read_settings(self.store), DEFAULTS)
        saved = save_settings(self.store, {"timezone": "Europe/Amsterdam", "max_runs_per_tick": 2,
                                           "default_provider": "openai"})
        self.assertEqual(saved["timezone"], "Europe/Amsterdam")
        self.assertEqual(saved["default_provider"], "openai")
        self.assertEqual(read_settings(self.store)["max_runs_per_tick"], 2)
        for invalid in ({"timezone": "Europe/Invalid"}, {"max_runs_per_tick": 0},
                        {"max_runs_per_tick": 2.5}, {"default_provider": "missing"},
                        {"confirm_cloud_each_run": False}, {"unexpected": True}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                save_settings(self.store, invalid)

    def test_credentials_are_not_exposed_in_provider_state(self) -> None:
        cloud = next(p for p in PROVIDERS if p["id"] == "openai")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "private-test-credential"}):
            state = provider_state(cloud)
        self.assertEqual(state["state"], "ready_to_test")
        self.assertTrue(state["credential_configured"])
        self.assertNotIn("private-test-credential", json.dumps(state))
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(provider_state(cloud)["state"], "needs_setup")
        azure = next(p for p in PROVIDERS if p["id"] == "azure")
        self.assertEqual(provider_state(azure)["state"], "needs_setup")

    def test_check_history_requires_a_real_test_and_resets_on_edit(self) -> None:
        local = next(p for p in PROVIDERS if p["id"] == "ollama")
        self.assertEqual(provider_states(self.store, [local])["ollama"]["state"], "ready_to_test")
        remember_check(self.store, "ollama", status="responded", model="sample", latency_ms=25)
        self.assertEqual(provider_states(self.store, [local])["ollama"]["state"], "responded")
        self.store.put_custom("provider", {**local, "model": "changed"})
        self.assertEqual(provider_states(self.store, [{**local, "model": "changed"}])["ollama"]["state"], "ready_to_test")

    def test_cloud_loopback_is_not_a_valid_destination(self) -> None:
        with self.assertRaises(ValueError):
            validate_url("https://127.0.0.1:9000/v1", False)
        with self.assertRaises(ValueError):
            validate_url("https://service.internal/v1", False)

    def test_model_catalog_parsing_and_bounded_response(self) -> None:
        local = next(p for p in PROVIDERS if p["id"] == "ollama")
        observed = {}
        class Stub:
            def open(self, request, timeout):
                observed["url"] = request.full_url
                observed["timeout"] = timeout
                return io.BytesIO(json.dumps({"data": [{"id": "local-model", "name": "Local Model"},
                                                      {"missing": "no-id"}]}).encode())
        with patch("phd_agents.connectivity.build_opener", return_value=Stub()):
            result = model_list(local)
        self.assertEqual(result["models"], [{"id": "local-model", "name": "Local Model"}])
        self.assertTrue(observed["url"].endswith("/v1/models"))
        self.assertEqual(observed["timeout"], 12)

    def test_local_settings_api_roundtrip(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with urlopen(base + "/api/settings", timeout=4) as response:
                self.assertEqual(json.load(response)["settings"]["default_provider"], "ollama")
            body = json.dumps({"default_provider": "openai", "timezone": "Europe/Amsterdam"}).encode()
            request = Request(base + "/api/settings", data=body,
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=4) as response:
                self.assertEqual(json.load(response)["settings"]["timezone"], "Europe/Amsterdam")
            with urlopen(base + "/api/settings", timeout=4) as response:
                self.assertEqual(json.load(response)["settings"]["default_provider"], "openai")
            bad = Request(base + "/api/settings", data=b'{"max_runs_per_tick":-1}',
                          headers={"Content-Type": "application/json"}, method="POST")
            with self.assertRaises(HTTPError) as raised:
                urlopen(bad, timeout=4)
            self.assertEqual(raised.exception.code, 400)
        finally:
            server.shutdown()
            worker.join(timeout=4)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
