from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from phd_agents.observability import report_observability
from phd_agents.server import ApiServer
from phd_agents.store import Store


class RedactedObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / "private.sqlite3")
        self.addCleanup(self.store.close)

    def test_inference_trace_sanitization_and_latency(self) -> None:
        self.store.put_run(
            "agent", "portfolio_planner", "PRIVATE-APP-99", "proposed", "ollama",
            {"text": "HIGHLY_SENSITIVE_ANSWER", "prompt": "HIGHLY_SENSITIVE_PROMPT",
             "source_url": "https://private.example", "api_key": "SECRET_0001",
             "latency_ms": 105, "usage": {"prompt_tokens": 40, "completion_tokens": 15}},
        )
        self.store.put_run(
            "agent", "deadline_auditor", "PRIVATE-APP-77", "failed", "ollama",
            {"error_type": "ProviderError", "error": "SECRET_0002",
             "latency_ms": 240, "usage": {"prompt_tokens": 10}},
        )
        report = report_observability(self.store)
        self.assertEqual(report["window"]["completed_calls"], 2)
        self.assertEqual(report["window"]["failed_calls"], 1)
        self.assertEqual(report["window"]["p95_latency_ms"], 240)
        self.assertEqual(report["objectives"]["status"], "insufficient_data")
        self.assertEqual(report["recent_traces"][0]["error_type"], "ProviderError")
        serialized = json.dumps(report)
        for private in ("HIGHLY_SENSITIVE", "SECRET_", "PRIVATE-APP-", "private.example", '"prompt"'):
            self.assertNotIn(private, serialized)

    def test_operator_objectives_require_adequate_measurement(self) -> None:
        for i in range(20):
            self.store.put_run(
                "agent", "portfolio_planner", None,
                "failed" if i == 0 else "proposed", "ollama",
                {"error_type": "ProviderError", "latency_ms": 1200},
            )
        passed = report_observability(self.store)
        self.assertEqual(passed["objectives"]["status"], "within_objectives")
        exceeded = report_observability(self.store, max_error_rate=0.04)
        self.assertEqual(exceeded["objectives"]["status"], "breached")
        latency = report_observability(self.store, max_p95_ms=1000)
        self.assertEqual(latency["objectives"]["status"], "breached")

    def test_invalid_clock_and_request_limits(self) -> None:
        with self.assertRaises(ValueError):
            report_observability(self.store, now=datetime.now(), sample_limit=10)
        with self.assertRaises(ValueError):
            report_observability(self.store, sample_limit=0)

    def test_private_http_report_does_not_expose_applicant_data(self) -> None:
        self.store.put_run("agent", "portfolio_planner", "SECRET_APP_19", "proposed", "ollama",
                           {"text": "SECRET_ANSWER", "latency_ms": 50})
        service = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.directory.name))
        worker = threading.Thread(target=service.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{service.server_port}/api/observability"
            with urlopen(url, timeout=6) as response:
                raw = response.read().decode()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(raw)["schema_version"], 1)
                self.assertNotIn("SECRET", raw)
        finally:
            service.shutdown()
            service.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
