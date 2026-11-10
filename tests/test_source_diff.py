from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from phd_agents.source_diff import compare_source_text
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text
from phd_agents.store import Store


class SourceDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "data.sqlite3")
        self.addCleanup(self.store.close)
        self.url = "https://university.example/program"

    def observe(self, text: str, app: str = "APP1") -> dict:
        raw = text.encode("utf-8")
        return observe_record(self.store, app, self.url, fetcher=lambda _: {
            "status": "fetched", "http_status": 200, "content_length": len(raw),
            "content_sha256": hashlib.sha256(raw).hexdigest(),
            **extract_visible_text(raw, "text/html"),
        })

    def test_date_change_is_an_unverified_review_hint(self) -> None:
        first = self.observe("<p>Application deadline: 15 December 2026.</p>")
        second = self.observe("<div>Application deadline: 20 December 2026.</div>")
        result = compare_source_text(self.store, second["id"])
        self.assertEqual(result["status"], "visible_text_changed")
        self.assertEqual(result["previous_id"], first["id"])
        self.assertTrue(result["comparison_complete"])
        self.assertIn("15", str(result["changes"]))
        self.assertIn("20", str(result["changes"]))
        self.assertIn("deadline", result["possible_topics"])
        self.assertFalse(result["semantic_claim_verified"])
        self.assertEqual(compare_source_text(self.store, first["id"])["status"], "no_preceding_observation")

    def test_markup_only_and_legacy_text_are_not_claim_changes(self) -> None:
        self.observe("<p>Funding is available to eligible applicants.</p>")
        latest = self.observe("<div>Funding is available to eligible applicants.</div>")
        self.assertEqual(compare_source_text(self.store, latest["id"])["status"], "visible_text_unchanged")
        self.store.db.execute(
            "INSERT INTO source_observations(application_id,source_url,status,observed_at)"
            " VALUES(?,?,?,?)", ("LEGACY", self.url, "fetched", "2026-11-08T00:00:00Z"),
        )
        self.store.db.commit()
        latest_legacy = self.observe("<p>Documents required.</p>", "LEGACY")
        self.assertEqual(compare_source_text(self.store, latest_legacy["id"])["status"], "text_unavailable")

    def test_unrelated_applications_are_not_compared(self) -> None:
        self.observe("<p>Deadline December 1.</p>", "OTHER")
        row = self.observe("<p>Deadline December 2.</p>", "APP1")
        self.assertEqual(compare_source_text(self.store, row["id"])["status"], "no_preceding_observation")


if __name__ == "__main__":
    unittest.main()
