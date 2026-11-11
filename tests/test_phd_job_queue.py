from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from phd_agents.job_queue import (
    cancel_job, claim_job, enqueue_local_agent, finish_job,
    job_status, list_jobs, worker_once,
)
from phd_agents.catalog import provider_spec
from phd_agents.engine import catalog, run_agent
from phd_agents.providers import ProviderError
from phd_agents.server import ApiServer
from phd_agents.store import ConflictError, Store


class DurableLocalQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "state.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)

    def make_job(self, **changes: object) -> dict:
        return enqueue_local_agent(self.store, agent_id="portfolio_planner",
                                   input_text="Audit source evidence", **changes)

    def test_job_persists_after_store_reopen_and_is_claimed_once(self) -> None:
        pending = self.make_job()
        reopened = Store(self.path)
        try:
            self.assertEqual(job_status(reopened, pending["id"])["status"], "queued")
            first = claim_job(reopened)
            self.assertIsNotNone(first)
            self.assertEqual(first[0], pending["id"])
            self.assertIsNone(claim_job(self.store))
            result = finish_job(reopened, *first, run_id="persisted-model-run")
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["run_id"], "persisted-model-run")
            self.assertEqual(result["attempts"], 1)
        finally:
            reopened.close()
        self.assertEqual(len(list_jobs(self.store)), 1)

    def test_queued_cancel_prevents_inference(self) -> None:
        pending = self.make_job()
        self.assertEqual(cancel_job(self.store, pending["id"])["status"], "canceled")
        with patch("phd_agents.job_queue.run_agent") as model:
            self.assertEqual(worker_once(self.store, self.root), {"status": "idle"})
            model.assert_not_called()

    def test_running_cancel_is_cooperative_not_false_success(self) -> None:
        pending = self.make_job()
        identity, token = claim_job(self.store)
        state = cancel_job(self.store, identity)
        self.assertEqual(state["status"], "running")
        self.assertTrue(state["cancel_requested"])
        finished = finish_job(self.store, identity, token, run_id="actual-run")
        self.assertEqual(finished["status"], "succeeded")
        self.assertTrue(finished["cancel_requested"])

    def test_worker_records_real_result_without_exposing_prompt(self) -> None:
        pending = self.make_job()
        with patch("phd_agents.job_queue.run_agent", return_value={"id": "run-actual"}) as model:
            result = worker_once(self.store, self.root)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["run_id"], "run-actual")
        self.assertEqual(model.call_args.kwargs["cloud_consent"], False)
        self.assertEqual(model.call_args.kwargs["provider_id"], "ollama")
        self.assertEqual(
            model.call_args.kwargs["expected_provider_fingerprint"],
            self.store.db.execute(
                "SELECT provider_fingerprint FROM worker_jobs WHERE id=?", (pending["id"],)
            ).fetchone()[0],
        )
        self.assertNotIn("Audit source evidence", json.dumps(result))
        self.assertEqual(job_status(self.store, pending["id"])["attempts"], 1)

    def test_bounded_local_failure_retry(self) -> None:
        pending = self.make_job(max_attempts=2)
        with patch("phd_agents.job_queue.run_agent", side_effect=ProviderError("synthetic outage")):
            retry = worker_once(self.store, self.root)
            self.assertEqual(retry["status"], "queued")
            self.assertEqual(retry["attempts"], 1)
            with self.store.db:
                self.store.db.execute("UPDATE worker_jobs SET available_at=? WHERE id=?",
                                      ("2020-01-01T00:00:00+00:00", pending["id"]))
            failed = worker_once(self.store, self.root)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["attempts"], 2)
        self.assertEqual(failed["error_type"], "ProviderError")
        self.assertEqual(worker_once(self.store, self.root), {"status": "idle"})

    def test_expired_lease_fences_late_worker_result(self) -> None:
        pending = self.make_job()
        first = claim_job(self.store)
        with self.store.db:
            self.store.db.execute("UPDATE worker_jobs SET lease_expires_at=? WHERE id=?",
                                  ("2020-01-01T00:00:00+00:00", pending["id"]))
        second = claim_job(self.store)
        self.assertNotEqual(first[1], second[1])
        with self.assertRaises(ConflictError):
            finish_job(self.store, *first, run_id="stale")
        self.assertEqual(finish_job(self.store, *second, run_id="current")["status"], "succeeded")

    def test_cloud_routes_rejected_before_queue_write(self) -> None:
        with self.assertRaises(PermissionError):
            self.make_job(provider_id="openai")
        self.assertEqual(list_jobs(self.store), [])

    def test_queue_fails_terminally_after_provider_reconfiguration(self) -> None:
        pending = self.make_job(max_attempts=3)
        provider = next(p for p in catalog(self.store)["providers"] if p["id"] == "ollama")
        self.store.put_custom("provider", provider_spec({**provider, "model": "replacement-model"}))
        with patch("phd_agents.job_queue.run_agent") as model:
            result = worker_once(self.store, self.root)
            model.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["error_type"], "ProviderRouteChanged")
        self.assertEqual(worker_once(self.store, self.root), {"status": "idle"})
        self.assertNotIn("Audit source evidence", json.dumps(result))

    def test_legacy_unpinned_job_is_not_executed(self) -> None:
        pending = self.make_job(max_attempts=3)
        with self.store.db:
            self.store.db.execute(
                "UPDATE worker_jobs SET provider_fingerprint=NULL WHERE id=?",
                (pending["id"],),
            )
        with patch("phd_agents.job_queue.run_agent") as model:
            result = worker_once(self.store, self.root)
            model.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "UnpinnedLegacyJob")
        self.assertEqual(result["attempts"], 1)

    def test_inflight_provider_edit_is_fenced_before_model_invocation(self) -> None:
        pending = self.make_job(max_attempts=3)

        def change_then_run(store, root, **kwargs):
            local = next(p for p in catalog(store)["providers"] if p["id"] == "ollama")
            store.put_custom("provider", provider_spec({**local, "model": "changed-inflight"}))
            return run_agent(store, root, **kwargs)

        with patch("phd_agents.job_queue.run_agent", side_effect=change_then_run):
            with patch("phd_agents.engine.invoke") as model:
                result = worker_once(self.store, self.root)
                model.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "ConflictError")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(job_status(self.store, pending["id"])["run_id"], None)

    def test_legacy_database_adds_nullable_fingerprint_column(self) -> None:
        old_path = self.root / "legacy.sqlite3"
        db = sqlite3.connect(old_path)
        db.execute("""
            CREATE TABLE worker_jobs(
                id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,provider_id TEXT NOT NULL,
                application_id TEXT,input_text TEXT NOT NULL,status TEXT NOT NULL,
                attempts INTEGER NOT NULL,max_attempts INTEGER NOT NULL,
                available_at TEXT NOT NULL,lease_token TEXT,lease_expires_at TEXT,
                run_id TEXT,error_type TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL
            )
        """)
        db.commit()
        db.close()
        old_path.chmod(0o600)
        reopened = Store(old_path)
        try:
            columns = {entry["name"] for entry in reopened.db.execute("PRAGMA table_info(worker_jobs)")}
            self.assertIn("provider_fingerprint", columns)
            new = enqueue_local_agent(
                reopened, agent_id="portfolio_planner", input_text="Queue a safe task"
            )
            self.assertEqual(new["status"], "queued")
            self.assertRegex(
                reopened.db.execute(
                    "SELECT provider_fingerprint FROM worker_jobs WHERE id=?", (new["id"],)
                ).fetchone()[0], r"^[a-f0-9]{64}$",
            )
        finally:
            reopened.close()

    def test_http_job_submission_status_and_cancel(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=self.root)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def post(path: str, payload: dict) -> dict:
                request = Request(base + path, data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=5) as response:
                    return json.load(response)
            sent = post("/api/jobs/enqueue", {"agent_id": "portfolio_planner",
                        "input_text": "Review my recorded documents"})
            identity = sent["job"]["id"]
            self.assertEqual(sent["job"]["status"], "queued")
            with urlopen(base + "/api/jobs/" + identity, timeout=5) as response:
                self.assertEqual(json.load(response)["status"], "queued")
            result = post("/api/jobs/" + identity + "/cancel", {})
            self.assertEqual(result["job"]["status"], "canceled")
            with urlopen(base + "/api/jobs", timeout=5) as response:
                self.assertEqual(json.load(response)["jobs"][0]["id"], identity)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
