from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.source_observer import (
    fetch_public_source, observe_record, recent_observations, run_source_observations,
)
from phd_agents.store import Store


class Response(io.BytesIO):
    def __init__(self, body: bytes, media: str = "text/html"):
        super().__init__(body)
        self.headers = {"Content-Type": media}


class FakeTransport:
    def __init__(self, body: bytes, media: str = "text/html"):
        self.body = body
        self.media = media
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return Response(self.body, self.media)


class PrivateSourceObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "private.sqlite3")
        self.addCleanup(self.store.close)
        self.url = "https://university.example.edu/doctoral"

    def test_transport_hash_only_and_no_credentials(self):
        fake = FakeTransport(b"<html>University source</html>")
        with patch("phd_agents.source_observer.build_opener", return_value=fake) as opened:
            observed = fetch_public_source(self.url)
        self.assertEqual(observed["status"], "fetched")
        self.assertEqual(observed["content_sha256"], hashlib.sha256(fake.body).hexdigest())
        self.assertFalse(fake.calls[0][0].has_header("Authorization"))
        self.assertEqual(len(opened.call_args.args), 3)

    def test_byte_drift_only_requires_manual_review(self):
        first = {"status": "fetched", "http_status": 200,
                 "content_sha256": hashlib.sha256(b"first").hexdigest(), "content_length": 5}
        second = {**first, "content_sha256": hashlib.sha256(b"second").hexdigest()}
        results = [
            observe_record(self.store, "APP1", self.url, fetcher=lambda _: item)
            for item in (first, first, second)
        ]
        self.assertEqual([x["drift"] for x in results],
                         ["baseline_only", "unchanged_bytes", "source_bytes_changed_needs_review"])
        history = recent_observations(self.store)
        self.assertEqual(len(history), 3)
        self.assertEqual([item["drift"] for item in reversed(history)],
                         ["baseline_only", "unchanged_bytes", "source_bytes_changed_needs_review"])
        self.assertEqual(self.store.list_applications(), {})

    def test_existing_observation_schema_migrates_preserving_history(self):
        import sqlite3
        db_path = self.root / "legacy.sqlite3"
        db = sqlite3.connect(db_path)
        db.execute("CREATE TABLE source_observations (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id TEXT NOT NULL, source_url TEXT NOT NULL, status TEXT NOT NULL, content_sha256 TEXT, observed_at TEXT NOT NULL, http_status INTEGER, content_length INTEGER)")
        db.execute("INSERT INTO source_observations(application_id,source_url,status,observed_at) VALUES(?,?,?,?)",
                   ("legacy", self.url, "http_error", "2026-11-09T00:00:00+00:00"))
        db.commit()
        db.close()
        with Store(db_path) as migrated:
            history = recent_observations(migrated)
            self.assertEqual(len(history), 1)
            self.assertIsNone(history[0]["drift"])
            result = observe_record(migrated, "legacy", self.url,
                                    fetcher=lambda _: {"status": "http_error", "http_status": 404,
                                                       "content_sha256": None, "content_length": 0})
            self.assertEqual(result["drift"], "unavailable_no_source_conclusion")
            self.assertEqual(recent_observations(migrated)[0]["drift"], result["drift"])

    def test_unsupported_media_and_unsafe_endpoints(self):
        fake = FakeTransport(b"%PDF-1.5", "application/pdf")
        with patch("phd_agents.source_observer.build_opener", return_value=fake):
            response = fetch_public_source(self.url)
        self.assertEqual(response["status"], "unsupported_media_type")
        event = observe_record(self.store, "APP2", self.url, fetcher=lambda _: response)
        self.assertEqual(event["drift"], "unavailable_no_source_conclusion")
        for endpoint in ("https://127.0.0.1/source", "https://university.example.edu/?key=secret"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                fetch_public_source(endpoint)

    def test_manual_run_only_approved_records(self):
        records = [
            {"id": "A", "record_type": "tracked", "verification": "source_verified",
             "source_url": self.url},
            {"id": "B", "record_type": "tracked", "verification": "unverified",
             "source_url": "https://unknown.example.edu"},
            {"id": "C", "record_type": "tracked", "verification": "source_verified",
             "source_url": "http://localhost:8000/api"},
        ]
        body = {"status": "fetched", "http_status": 200,
                "content_sha256": hashlib.sha256(b"html").hexdigest(), "content_length": 4}
        with patch("phd_agents.source_observer.owner_records", return_value=({}, records)), patch(
            "phd_agents.source_observer.fetch_public_source", return_value=body
        ) as network:
            result = run_source_observations(self.store, self.root, limit=10)
        self.assertEqual(result["network_requests"], 1)
        self.assertEqual(network.call_count, 1)
        self.assertEqual({x["reason"] for x in result["skipped"]},
                         {"source_not_reviewed", "unsafe_or_missing_url"})


if __name__ == "__main__":
    unittest.main()
