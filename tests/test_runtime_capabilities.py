from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from phd_agents.capabilities import private_runtime_capabilities
from phd_agents.server import ApiServer
from phd_agents.store import Store


class PrivateCapabilitiesTests(unittest.TestCase):
    def test_model_readiness_is_distinct_from_server_availability(self) -> None:
        report = private_runtime_capabilities(provider_verified=False, provider_name="Local model")
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["capabilities"]["private_state"]["ready"])
        self.assertFalse(report["capabilities"]["interactive_inference"]["ready"])
        self.assertTrue(report["capabilities"]["local_background_jobs"]["ready"])
        self.assertIn("operator_started_worker", report["capabilities"]["local_background_jobs"]["requires"])
        self.assertFalse(report["capabilities"]["authenticated_cloud"]["supported"])
        self.assertTrue(private_runtime_capabilities(provider_verified=True)["capabilities"]["agent_execution"]["ready"])

    def test_native_streaming_requires_compatible_verified_model(self) -> None:
        from phd_agents.capabilities import private_runtime_capabilities

        pending = private_runtime_capabilities(provider_verified=False, provider_kind="openai_compatible")
        self.assertFalse(pending["capabilities"]["native_streaming"]["ready"])
        compatible = private_runtime_capabilities(provider_verified=True, provider_kind="openai_compatible")
        self.assertTrue(compatible["capabilities"]["native_streaming"]["ready"])
        unsupported = private_runtime_capabilities(provider_verified=True, provider_kind="anthropic")
        self.assertFalse(unsupported["capabilities"]["native_streaming"]["ready"])

    def test_capabilities_endpoint_does_not_expose_private_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / "state.sqlite3")
            server = ApiServer(("127.0.0.1", 0), store=store, root=Path(temp))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/capabilities", timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.load(response)
                self.assertEqual(payload["mode"], "private_loopback")
                self.assertTrue(payload["security"]["loopback_only"])
                self.assertFalse(payload["capabilities"]["authenticated_cloud"]["ready"])
                self.assertNotIn("credentials", json.dumps(payload))
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                store.close()


if __name__ == "__main__":
    unittest.main()
