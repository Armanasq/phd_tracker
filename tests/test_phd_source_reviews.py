from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.source_observer import recent_observations
from phd_agents.source_reviews import record_source_review
from phd_agents.store import Store


class SourceReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "reviews.sqlite3")
        self.addCleanup(self.store.close)
        self.digest = hashlib.sha256(b"verified fetch bytes").hexdigest()
        self.store.db.execute(
            "INSERT INTO source_observations(application_id,source_url,status,content_sha256,"
            "observed_at,http_status,content_length,drift) VALUES(?,?,?,?,?,?,?,?)",
            ("APP1", "https://university.example/doctorate", "fetched", self.digest,
             "2026-11-10T08:00:00+00:00", 200, 20, "source_bytes_changed_needs_review"),
        )
        self.store.db.commit()
        self.observation_id = self.store.db.execute(
            "SELECT id FROM source_observations ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]

    def test_review_is_private_append_only_and_idempotent(self) -> None:
        data = dict(observation_id=self.observation_id, decision="needs_follow_up",
                    note="Source body changed; institutional facts need review.",
                    expected_digest=self.digest)
        first = record_source_review(self.store, **data)
        second = record_source_review(self.store, **data)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list_applications()), 0)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM source_observation_reviews"
        ).fetchone()[0], 1)
        history = recent_observations(self.store)
        self.assertEqual(history[0]["review_decision"], "needs_follow_up")
        self.assertEqual(history[0]["id"], self.observation_id)
        self.assertNotIn("Source body changed", json.dumps(history))
        reviewed = record_source_review(
            self.store, observation_id=self.observation_id,
            decision="reviewed_no_fact_change",
            note="Primary record was examined and only layout markup changed.",
            expected_digest=self.digest,
        )
        self.assertFalse(reviewed["reused"])
        self.assertEqual(recent_observations(self.store)[0]["review_decision"], "reviewed_no_fact_change")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM source_observation_reviews"
        ).fetchone()[0], 2)

    def test_invalid_review_never_mutates_data(self) -> None:
        data = dict(observation_id=self.observation_id, decision="needs_follow_up",
                    note="Check verified primary source against prior evidence.",
                    expected_digest=self.digest)
        invalid = [
            {**data, "observation_id": True},
            {**data, "observation_id": 0},
            {**data, "observation_id": 98765},
            {**data, "decision": "source_verified"},
            {**data, "note": "too short"},
            {**data, "expected_digest": "0" * 64},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                record_source_review(self.store, **item)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM source_observation_reviews"
        ).fetchone()[0], 0)

    def test_local_api_accepts_review_and_rejects_stale_digest(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.tmp.name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host = f"http://127.0.0.1:{server.server_port}"
        try:
            document = {
                "observation_id": self.observation_id,
                "decision": "needs_follow_up",
                "note": "Manual evidence review required after this source changed.",
                "expected_digest": self.digest,
            }
            req = Request(host + "/api/source-observations/review",
                          data=json.dumps(document).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=5) as reply:
                self.assertEqual(json.load(reply)["review"]["authority"], "owner_attestation_only")
            with urlopen(host + "/api/source-observations", timeout=5) as reply:
                observed = json.load(reply)["observations"]
            self.assertEqual(observed[0]["review_decision"], "needs_follow_up")
            self.assertNotIn("review note", json.dumps(observed).lower())
            req_bad = Request(host + "/api/source-observations/review",
                              data=json.dumps({**document, "expected_digest": None}).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            with self.assertRaises(HTTPError) as error:
                urlopen(req_bad, timeout=5)
            self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
