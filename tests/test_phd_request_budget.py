from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.request_budget import RequestBudget
from phd_agents.server import ApiServer
from phd_agents.store import Store


class BoundedRateBudgetTests(unittest.TestCase):
    def test_sliding_windows_are_bounded_and_reset_at_window_edge(self) -> None:
        budget = RequestBudget(inference_per_minute=2, writes_per_minute=4)
        self.assertTrue(budget.admit("inference", now=100))
        self.assertTrue(budget.admit("inference", now=101))
        self.assertFalse(budget.admit("inference", now=101))
        self.assertTrue(budget.admit("inference", now=160))
        self.assertTrue(budget.admit("write", now=160))
        with self.assertRaises(ValueError):
            budget.admit("unexpected", now=160)

    def test_racing_threads_never_exceed_budget(self) -> None:
        budget = RequestBudget(inference_per_minute=8)
        with ThreadPoolExecutor(max_workers=25) as pool:
            allowed = list(pool.map(lambda _: budget.admit("inference", now=300), range(80)))
        self.assertEqual(sum(allowed), 8)

    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RequestBudget(inference_per_minute=0)
        with self.assertRaises(ValueError):
            RequestBudget(writes_per_minute=20000)
        with self.assertRaises(ValueError):
            RequestBudget(inference_per_minute=True)

    def test_http_admission_exhaustion_preserves_health_and_no_model_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "private.sqlite3")
            service = ApiServer(("127.0.0.1", 0), store=store, root=Path(folder))
            service.request_budget = RequestBudget(inference_per_minute=1, writes_per_minute=2)
            worker = threading.Thread(target=service.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{service.server_port}"
                def post():
                    request = Request(url + "/api/agents/run", data=json.dumps({
                        "agent_id": "portfolio_planner", "input_text": "Compare documented evidence"
                    }).encode(), headers={"Content-Type": "application/json"}, method="POST")
                    return urlopen(request, timeout=6)
                with patch("phd_agents.server.run_agent", return_value={"status": "proposed"}) as agent:
                    with post() as response:
                        self.assertEqual(response.status, 200)
                    with self.assertRaises(HTTPError) as rejected:
                        post()
                    self.assertEqual(rejected.exception.code, 429)
                    self.assertEqual(agent.call_count, 1)
                with urlopen(url + "/api/health", timeout=6) as response:
                    self.assertEqual(response.status, 200)
            finally:
                service.shutdown()
                service.server_close()
                worker.join(timeout=5)
                store.close()


if __name__ == "__main__":
    unittest.main()
