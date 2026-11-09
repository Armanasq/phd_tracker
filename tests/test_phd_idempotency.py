from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.store import Store


class RequestIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "private.sqlite3")
        self.addCleanup(self.store.close)
        self.server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 4)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def post(self, key: str, *, task: str = "Robotics", route: str = "/api/agents/run") -> dict:
        payload = ({"agent_id": "research_fit", "input_text": task} if route.endswith("/agents/run")
                   else {"workflow_id": "application_preflight", "input_text": task})
        request = Request(
            self.url + route, method="POST",
            headers={"Content-Type": "application/json", "Idempotency-Key": key},
            data=json.dumps(payload).encode("utf-8"),
        )
        with urlopen(request, timeout=8) as response:
            return json.load(response)

    def test_repeated_request_returns_original_inference_without_repeat(self) -> None:
        key = uuid.uuid4().hex
        with patch("phd_agents.server.run_agent", return_value={"id": "run-1", "text": "Evidence only"}) as model:
            first = self.post(key)
            second = self.post(key)
        self.assertEqual(first, second)
        self.assertEqual(model.call_count, 1)
        with self.assertRaises(HTTPError) as error:
            self.post(key, task="Changed task")
        self.assertEqual(error.exception.code, 409)

    def test_same_key_is_exclusive_during_inference(self) -> None:
        key = uuid.uuid4().hex
        started, release = threading.Event(), threading.Event()

        def model(*args, **kwargs):
            started.set()
            if not release.wait(timeout=7):
                raise RuntimeError("Test timeout")
            return {"id": "once"}

        with patch("phd_agents.server.run_agent", side_effect=model) as mocked:
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(self.post, key)
                self.assertTrue(started.wait(timeout=4))
                try:
                    with self.assertRaises(HTTPError) as error:
                        self.post(key)
                    self.assertEqual(error.exception.code, 409)
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=7)["id"], "once")
            self.assertEqual(self.post(key)["id"], "once")
            self.assertEqual(mocked.call_count, 1)

    def test_provider_failure_releases_key_for_retry(self) -> None:
        key = uuid.uuid4().hex
        with patch("phd_agents.server.run_agent", side_effect=RuntimeError("synthetic offline")):
            with self.assertRaises(HTTPError) as error:
                self.post(key)
            self.assertEqual(error.exception.code, 502)
        with patch("phd_agents.server.run_agent", return_value={"id": "recovered"}) as model:
            self.assertEqual(self.post(key)["id"], "recovered")
            self.assertEqual(model.call_count, 1)

    def test_key_input_validation(self) -> None:
        with self.assertRaises(HTTPError) as error:
            self.post("short")
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
