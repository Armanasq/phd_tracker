from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from phd_agents.catalog import workflow_spec
from phd_agents.engine import scheduler_once
from phd_agents.metrics import usage_summary
from phd_agents.server import ApiServer
from phd_agents.settings import save_settings
from phd_agents.store import Store


class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "private.sqlite3")
        self.addCleanup(self.store.close)

    def test_usage_is_measured_not_priced(self) -> None:
        self.store.put_run("agent", "portfolio_planner", None, "proposed", "ollama",
                           {"model": "local", "latency_ms": 100,
                            "usage": {"prompt_tokens": 110, "completion_tokens": 35}})
        self.store.put_run("agent", "portfolio_planner", None, "proposed", "ollama",
                           {"model": "local", "latency_ms": 300,
                            "usage": {"input_tokens": 150, "output_tokens": 45}})
        self.store.put_run("agent", "portfolio_planner", None, "failed", "openai",
                           {"model": "cloud", "error_type": "ProviderError"})
        report = usage_summary(self.store)
        self.assertEqual(report["sampled_runs"], 3)
        self.assertEqual(report["total_input_tokens"], 260)
        self.assertEqual(report["total_output_tokens"], 80)
        self.assertEqual(report["total_failed"], 1)
        self.assertIsNone(report["cost_estimate"])
        local = next(x for x in report["provider_usage"] if x["provider_id"] == "ollama")
        self.assertEqual(local["average_latency_ms"], 200)
        self.assertEqual(local["p95_latency_ms"], 300)
        self.assertEqual(local["measured_calls"], 2)
        self.assertEqual(usage_summary(self.store, sample_limit=1)["sampled_runs"], 1)
        with self.assertRaises(ValueError):
            usage_summary(self.store, sample_limit=0)

    def test_cloud_schedules_require_explicit_daily_budget(self) -> None:
        self.store.put_custom("workflow", workflow_spec({
            "id": "scheduled_cloud", "agent_id": "portfolio_planner",
            "steps": ["portfolio_planner", "deadline_auditor"],
            "schedule": "daily", "enabled": True, "cloud_consent": True,
            "provider_id": "openai"
        }))
        now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
        with patch("phd_agents.engine.run_workflow", return_value={"id": "run1"}) as run:
            disabled = scheduler_once(self.store, Path(self.folder.name), now=now)
            self.assertEqual(disabled[0]["reason"], "cloud_budget_disabled")
            save_settings(self.store, {"max_cloud_model_calls_per_day": 1})
            insufficient = scheduler_once(self.store, Path(self.folder.name), now=now)
            self.assertEqual(insufficient[0]["reason"], "daily_cloud_model_call_cap")
            save_settings(self.store, {"max_cloud_model_calls_per_day": 2})
            approved = scheduler_once(self.store, Path(self.folder.name), now=now)
            self.assertEqual(approved[0]["status"], "proposed")
            self.assertEqual(run.call_count, 1)
        for invalid in (-1, 101, 0.5, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                save_settings(self.store, {"max_cloud_model_calls_per_day": invalid})

    def test_private_metrics_endpoint(self) -> None:
        self.store.put_run("agent", "test", None, "proposed", "ollama",
                           {"model": "local", "usage": {"prompt_tokens": 7, "completion_tokens": 5}})
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.folder.name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen("http://127.0.0.1:" + str(server.server_port) + "/api/metrics", timeout=4) as response:
                data = json.load(response)
                self.assertEqual(data["total_input_tokens"], 7)
                self.assertEqual(data["provider_usage"][0]["calls"], 1)
        finally:
            server.shutdown()
            thread.join(timeout=4)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
