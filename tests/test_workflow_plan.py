from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from phd_agents.catalog import workflow_spec
from phd_agents.engine import run_workflow, workflow_plan
from phd_agents.server import ApiServer
from phd_agents.settings import save_settings
from phd_agents.store import Store


class WorkflowPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "private.sqlite3")
        self.addCleanup(self.store.close)
        self.store.put_custom("workflow", workflow_spec({
            "id": "mixed_routes",
            "label": "Mixed routes",
            "agent_id": "portfolio_planner",
            "steps": ["portfolio_planner", "research_fit"],
            "schedule": "manual",
            "provider_id": "auto",
            "cloud_consent": False,
            "prompt": "Review evidence",
        }))
        save_settings(self.store, {"agent_routes": {"portfolio_planner": "ollama", "research_fit": "openai"}})

    def test_second_stage_cloud_blocked_before_first_model_call(self) -> None:
        planned = workflow_plan(self.store, workflow_id="mixed_routes")
        self.assertEqual(planned["model_calls"], 2)
        self.assertFalse(planned["manual_ready"])
        self.assertEqual(planned["stages"][1]["provider_id"], "openai")
        self.assertEqual(planned["blockers"], ["cloud_disclosure_consent_required"])
        with patch("phd_agents.engine.invoke") as invoke:
            with self.assertRaises(PermissionError):
                run_workflow(self.store, self.root, workflow_id="mixed_routes")
            invoke.assert_not_called()

    def test_explicit_consent_does_not_imply_provider_approval(self) -> None:
        planned = workflow_plan(self.store, workflow_id="mixed_routes", cloud_consent=True)
        self.assertTrue(planned["manual_ready"])
        self.assertFalse(planned["scheduled_policy_approved"])
        self.assertEqual(planned["stages"][0]["route_source"], "agent_assignment")

    def test_invalid_second_route_fails_before_inference(self) -> None:
        save_settings(self.store, {"agent_routes": {"portfolio_planner": "ollama", "research_fit": "openai"}})
        with self.assertRaises(ValueError):
            workflow_plan(self.store, workflow_id="not_a_workflow")

    def test_http_preview_returns_public_route_metadata_only(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=self.root)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url=f"http://127.0.0.1:{server.server_port}/api/workflows/preview"
            request=Request(url, data=json.dumps({"workflow_id": "mixed_routes"}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=5) as response:
                payload=json.load(response)
            self.assertEqual(payload["stages"][0]["provider_id"], "ollama")
            self.assertEqual(payload["stages"][1]["provider_id"], "openai")
            self.assertNotIn("api_key_env", json.dumps(payload))
            self.assertNotIn("base_url", json.dumps(payload))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
