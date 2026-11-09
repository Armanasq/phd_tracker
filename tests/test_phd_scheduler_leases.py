from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from phd_agents.catalog import workflow_spec
from phd_agents.engine import scheduler_once
from phd_agents.store import ConflictError, Store


class SchedulerLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "state.sqlite3"
        self.first, self.second = Store(self.path), Store(self.path)
        self.addCleanup(self.second.close)
        self.addCleanup(self.first.close)
        self.now = datetime(2026, 11, 9, 8, tzinfo=timezone.utc)

    def test_leases_are_exclusive_and_success_marking_is_owned(self) -> None:
        token, status = self.first.schedule_claim("daily", "2026-11-09", now=self.now)
        self.assertEqual(status, "claimed")
        self.assertIsNotNone(token)
        self.assertEqual(
            self.second.schedule_claim("daily", "2026-11-09", now=self.now),
            (None, "already_running"),
        )
        with self.assertRaises(ConflictError):
            self.second.schedule_complete("daily", "2026-11-09", "invalid")
        self.first.schedule_complete("daily", "2026-11-09", token)
        self.assertEqual(self.second.schedule_last("daily"), "2026-11-09")
        self.assertEqual(
            self.second.schedule_claim("daily", "2026-11-09", now=self.now),
            (None, "already_executed"),
        )

    def test_crashed_process_lease_recovers_after_expiration(self) -> None:
        first, _ = self.first.schedule_claim("daily", "2026-11-09", now=self.now)
        self.assertEqual(
            self.second.schedule_claim("daily", "2026-11-09", now=self.now + timedelta(seconds=200)),
            (None, "already_running"),
        )
        later, status = self.second.schedule_claim(
            "daily", "2026-11-09", now=self.now + timedelta(seconds=901)
        )
        self.assertEqual(status, "claimed")
        self.assertNotEqual(first, later)
        self.assertFalse(self.first.schedule_release("daily", "2026-11-09", first))
        self.second.schedule_complete("daily", "2026-11-09", later)

    def test_cloud_quota_reserves_active_scheduled_requests(self) -> None:
        first, status = self.first.schedule_claim(
            "flow-a", "2026-11-09", now=self.now,
            cloud_calls=1, cloud_cap=1, cloud_ids=["openai"], day_start="2026-11-09T00:00:00+00:00",
        )
        self.assertEqual(status, "claimed")
        self.assertEqual(
            self.second.schedule_claim(
                "flow-b", "2026-11-09", now=self.now,
                cloud_calls=1, cloud_cap=1, cloud_ids=["openai"], day_start="2026-11-09T00:00:00+00:00",
            ),
            (None, "daily_cloud_model_call_cap"),
        )
        self.assertTrue(self.first.schedule_release("flow-a", "2026-11-09", first))
        next_token, status = self.second.schedule_claim(
            "flow-b", "2026-11-09", now=self.now,
            cloud_calls=1, cloud_cap=1, cloud_ids=["openai"], day_start="2026-11-09T00:00:00+00:00",
        )
        self.assertEqual(status, "claimed")
        self.second.schedule_complete("flow-b", "2026-11-09", next_token)

    def test_double_scheduler_tick_runs_model_once(self) -> None:
        self.first.put_custom("workflow", workflow_spec({
            "id": "daily_test", "agent_id": "portfolio_planner", "provider_id": "ollama",
            "schedule": "daily", "enabled": True,
        }))
        started, release = threading.Event(), threading.Event()
        count = []

        def run(*args, **kwargs):
            count.append(kwargs["workflow_id"])
            started.set()
            if not release.wait(timeout=8):
                raise RuntimeError("Simulated inference timeout")
            return {"id": "one-run"}

        with patch("phd_agents.engine.run_workflow", side_effect=run):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(scheduler_once, self.first, self.root, now=self.now)
                self.assertTrue(started.wait(timeout=4))
                while_running = scheduler_once(self.second, self.root, now=self.now)
                self.assertEqual(while_running, [
                    {"workflow_id": "daily_test", "status": "skipped", "reason": "already_running"},
                ])
                release.set()
                self.assertEqual(future.result(timeout=8)[0]["status"], "proposed")
        self.assertEqual(count, ["daily_test"])
        self.assertEqual(scheduler_once(self.second, self.root, now=self.now), [])

    def test_failed_execution_releases_claim_for_retry(self) -> None:
        self.first.put_custom("workflow", workflow_spec({
            "id": "daily_fail", "agent_id": "portfolio_planner", "provider_id": "ollama",
            "schedule": "daily", "enabled": True,
        }))
        with patch("phd_agents.engine.run_workflow", side_effect=RuntimeError("offline")):
            result = scheduler_once(self.first, self.root, now=self.now)
        self.assertEqual(result[0]["status"], "failed")
        self.assertIsNone(self.first.schedule_last("daily_fail"))
        with patch("phd_agents.engine.run_workflow", return_value={"id": "retry"}):
            retry = scheduler_once(self.second, self.root, now=self.now)
        self.assertEqual(retry[0]["status"], "proposed")
        self.assertEqual(self.first.schedule_last("daily_fail"), "2026-11-09")


if __name__ == "__main__":
    unittest.main()
