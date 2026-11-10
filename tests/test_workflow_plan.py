from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from phd_agents.catalog import provider_spec, workflow_spec
from phd_agents.engine import WorkflowExecutionError, catalog, run_agent, run_workflow, workflow_plan
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

    def test_multi_stage_requires_verified_models_before_first_call(self) -> None:
        preview = workflow_plan(self.store, workflow_id="mixed_routes", cloud_consent=True)
        self.assertTrue(preview["manual_ready"])
        self.assertFalse(preview["execution_ready"])
        self.assertEqual(set(preview["model_probe_required"]), {"ollama", "openai"})
        with patch("phd_agents.engine.invoke") as invoke:
            with self.assertRaisesRegex(ValueError, "Verify inference"):
                run_workflow(self.store, self.root, workflow_id="mixed_routes",
                             cloud_consent=True)
            invoke.assert_not_called()

    def test_verified_multi_stage_routes_do_not_trigger_extra_probe_calls(self) -> None:
        status = {"ollama": {"state": "responded"}, "openai": {"state": "responded"}}
        def proposal(store, root, *, agent_id, **kwargs):
            return {"id": "run-" + agent_id, "agent_id": agent_id,
                    "text": "Evidence review pending", "usage": {}, "tools": []}
        with patch("phd_agents.engine.provider_states", return_value=status):
            preview = workflow_plan(self.store, workflow_id="mixed_routes", cloud_consent=True)
            self.assertTrue(preview["execution_ready"])
            self.assertEqual(preview["model_probe_required"], [])
            with patch("phd_agents.engine.run_agent", side_effect=proposal) as call:
                result = run_workflow(self.store, self.root, workflow_id="mixed_routes",
                                      cloud_consent=True)
            self.assertEqual(len(result["steps"]), 2)
            self.assertEqual(call.call_count, 2)

    def test_partial_stage_failure_has_durable_audit_and_no_retry_inference(self) -> None:
        from phd_agents.engine import WorkflowExecutionError
        from phd_agents.providers import ProviderError

        states = {"ollama": {"state": "responded"}, "openai": {"state": "responded"}}

        def fake_run(store, root, *, agent_id, **kwargs):
            if agent_id == "portfolio_planner":
                return {"id": "run-first", "agent_id": agent_id,
                        "text": "Unverified first-stage proposal", "usage": {}, "tools": []}
            raise ProviderError("Sensitive upstream error should not be copied into audit")

        with patch("phd_agents.engine.provider_states", return_value=states):
            with patch("phd_agents.engine.run_agent", side_effect=fake_run) as called:
                with self.assertRaises(WorkflowExecutionError) as raised:
                    run_workflow(self.store, self.root, workflow_id="mixed_routes",
                                 cloud_consent=True)
        self.assertEqual(called.call_count, 2)
        self.assertEqual(called.call_args_list[0].kwargs["provider_id"], "ollama")
        self.assertEqual(called.call_args_list[1].kwargs["provider_id"], "openai")
        error = raised.exception
        self.assertEqual(error.stage, 2)
        rows = [row for row in self.store.runs() if row["kind"] == "workflow_summary"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "failed")
        self.assertEqual(rows[0]["failed_stage"], 2)
        self.assertEqual(rows[0]["completed_run_ids"], ["run-first"])
        self.assertEqual(rows[0]["error_type"], "ProviderError")
        self.assertNotIn("Sensitive upstream error", json.dumps(rows))

    def test_provider_edit_between_stages_is_fenced_before_second_inference(self) -> None:
        states = {"ollama": {"state": "responded"}, "openai": {"state": "responded"}}
        actual_run_agent = run_agent

        def stage(store, root, *, agent_id, **kwargs):
            if agent_id == "portfolio_planner":
                configured = next(p for p in catalog(store)["providers"] if p["id"] == "openai")
                store.put_custom("provider", provider_spec({
                    **configured, "model": "provider-model-changed-during-workflow",
                }))
                return {"id": "first-stage", "agent_id": agent_id,
                        "text": "Unverified proposal", "usage": {}, "tools": []}
            return actual_run_agent(store, root, agent_id=agent_id, **kwargs)

        with patch("phd_agents.engine.provider_states", return_value=states):
            with patch("phd_agents.engine.run_agent", side_effect=stage) as calls:
                with patch("phd_agents.engine.invoke") as model:
                    with self.assertRaises(WorkflowExecutionError) as failed:
                        run_workflow(self.store, self.root, workflow_id="mixed_routes",
                                     cloud_consent=True)
                    model.assert_not_called()
        self.assertEqual(calls.call_count, 2)
        self.assertEqual(failed.exception.stage, 2)
        summary = next(row for row in self.store.runs() if row["kind"] == "workflow_summary")
        self.assertEqual(summary["error_type"], "ConflictError")
        self.assertEqual(summary["completed_run_ids"], ["first-stage"])
        self.assertEqual(summary["failed_provider_id"], "openai")

    def test_successful_workflow_records_a_separate_execution_summary(self) -> None:
        states = {"ollama": {"state": "responded"}, "openai": {"state": "responded"}}

        def fake_run(store, root, *, agent_id, **kwargs):
            return {"id": "run-" + agent_id, "agent_id": agent_id,
                    "text": "Unverified proposal", "usage": {}, "tools": []}

        with patch("phd_agents.engine.provider_states", return_value=states):
            with patch("phd_agents.engine.run_agent", side_effect=fake_run):
                result = run_workflow(self.store, self.root,
                                      workflow_id="mixed_routes", cloud_consent=True)
        summary = next(row for row in self.store.runs() if row["kind"] == "workflow_summary")
        self.assertEqual(result["workflow_execution_id"], summary["id"])
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(summary["completed_run_ids"], ["run-portfolio_planner", "run-research_fit"])
        self.assertEqual(summary["provider_routes"], ["ollama", "openai"])
        self.assertEqual(summary["status"], "proposed")
        self.assertNotIn("Unverified proposal", json.dumps(summary))

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
