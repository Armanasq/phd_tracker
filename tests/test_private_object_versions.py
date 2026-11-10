from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.store import ConflictError, Store


class PrivateObjectVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"

    def test_atomic_cross_tab_compare_and_swap_and_delete(self) -> None:
        first, second = Store(self.path), Store(self.path)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        created = first.put_item("referee", {"id": "person1", "name": "Referee A"}, expected_version=0)
        self.assertEqual(created["version"], 1)
        initial = second.items("referee")[0]
        self.assertEqual(initial["version"], 1)
        saved = first.put_item("referee", {"id": "person1", "name": "Referee B"}, expected_version=1)
        self.assertEqual(saved["version"], 2)
        with self.assertRaises(ConflictError):
            second.put_item("referee", {"id": "person1", "name": "Stale overwrite"}, expected_version=1)
        self.assertEqual(first.items("referee")[0]["name"], "Referee B")
        with self.assertRaises(ConflictError):
            second.delete_item("referee", "person1", expected_version=1)
        self.assertTrue(second.delete_item("referee", "person1", expected_version=2))
        with self.assertRaises(ConflictError):
            first.put_item("referee", {"id": "person1", "name": "Recreated incorrectly"}, expected_version=1)

    def test_existing_database_receives_non_destructive_version_migration(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE private_objects(kind TEXT NOT NULL,id TEXT NOT NULL,"
                               "payload TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(kind,id))")
            connection.execute(
                "INSERT INTO private_objects(kind,id,payload,updated_at) VALUES(?,?,?,?)",
                ("profile", "applicant", json.dumps({"id": "applicant", "skills": ["SLAM"]}),
                 "2026-11-09T12:00:00+00:00"),
            )
        store = Store(self.path)
        self.addCleanup(store.close)
        original = store.items("profile")[0]
        self.assertEqual(original["version"], 1)
        self.assertEqual(original["skills"], ["SLAM"])
        updated = store.put_item(
            "profile", {"id": "applicant", "skills": ["SLAM", "planning"]}, expected_version=1
        )
        self.assertEqual(updated["version"], 2)

    def test_http_api_requires_version_and_rejects_stale_edits(self) -> None:
        store = Store(self.path)
        server = ApiServer(("127.0.0.1", 0), store=store, root=Path(self.temp.name))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def post(url: str, payload: dict) -> tuple[int, dict]:
                request = Request(base + url, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urlopen(request, timeout=5) as response:
                        return response.status, json.load(response)
                except HTTPError as error:
                    return error.code, json.load(error)
            status, data = post("/api/private/referee", {
                "id": "ref1", "name": "Faculty A", "expected_version": 0
            })
            self.assertEqual(status, 200)
            self.assertEqual(data["entry"]["version"], 1)
            bad_status, _ = post("/api/private/referee", {"id": "ref1", "name": "Stale A"})
            self.assertEqual(bad_status, 400)
            status, _ = post("/api/private/referee", {
                "id": "ref1", "name": "Faculty B", "expected_version": 1
            })
            self.assertEqual(status, 200)
            conflict, _ = post("/api/private/referee", {
                "id": "ref1", "name": "Stale C", "expected_version": 1
            })
            self.assertEqual(conflict, 409)
            self.assertEqual(store.items("referee")[0]["name"], "Faculty B")
            stale_delete, _ = post("/api/private/referee/ref1/delete", {"expected_version": 1})
            self.assertEqual(stale_delete, 409)
            proper_delete, _ = post("/api/private/referee/ref1/delete", {"expected_version": 2})
            self.assertEqual(proper_delete, 200)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
            store.close()


if __name__ == "__main__":
    unittest.main()
