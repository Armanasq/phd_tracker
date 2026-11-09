from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.store import Store


class RuntimeBackpressureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "private.sqlite3")
        self.addCleanup(self.store.close)
        self.server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.worker.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def post(self) -> dict:
        request = Request(
            self.url + "/api/agents/run", method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"agent_id": "research_fit", "input_text": "Robotics"}).encode("utf-8"),
        )
        with urlopen(request, timeout=7) as response:
            return json.load(response)

    def test_rate_limiting_preserves_health_and_trace_identifiers(self) -> None:
        started, release = threading.Event(), threading.Event()
        active = 0
        lock = threading.Lock()

        def slow_run(*args, **kwargs):
            nonlocal active
            with lock:
                active += 1
                if active == 2:
                    started.set()
            if not release.wait(timeout=6):
                raise RuntimeError("Artificial test timeout")
            return {"status": "proposed", "text": "Validated result"}

        with patch("phd_agents.server.run_agent", side_effect=slow_run):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.post)
                second = pool.submit(self.post)
                try:
                    self.assertTrue(started.wait(timeout=5))
                    with urlopen(self.url + "/api/health", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(len(response.headers["X-Request-ID"]), 32)
                    with self.assertRaises(HTTPError) as rejected:
                        self.post()
                    self.assertEqual(rejected.exception.code, 429)
                    self.assertEqual(len(rejected.exception.headers["X-Request-ID"]), 32)
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=7)["status"], "proposed")
                self.assertEqual(second.result(timeout=7)["status"], "proposed")

    def test_configured_limit_is_bounded(self) -> None:
        with patch.dict(os.environ, {"PHDAI_MAX_CONCURRENT_INFERENCE": "0"}):
            with self.assertRaises(ValueError):
                ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        with patch.dict(os.environ, {"PHDAI_MAX_CONCURRENT_INFERENCE": "invalid"}):
            with self.assertRaises(ValueError):
                ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))


if __name__ == "__main__":
    unittest.main()
