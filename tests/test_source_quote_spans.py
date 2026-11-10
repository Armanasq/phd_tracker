from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from phd_agents.source_claims import capture_source_claim, observation_text, source_claims
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text
from phd_agents.store import Store


class SourceQuoteSpanTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "state.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.url = "https://university.example/program"

    def observe(self, text: str) -> dict:
        raw = text.encode("utf-8")
        return observe_record(self.store, "APP1", self.url,
            fetcher=lambda _: {"status": "fetched", "http_status": 200,
                               "content_length": len(raw),
                               "content_sha256": hashlib.sha256(raw).hexdigest(),
                               **extract_visible_text(raw, "text/plain")})

    def capture(self, record: dict, quote: str) -> dict:
        return capture_source_claim(
            self.store, observation_id=record["id"], claim_type="deadline",
            quote=quote, candidate_value="2026-12-15",
            expected_digest=record["content_sha256"],
        )

    def test_unique_span_is_anchored_to_unchanged_normalized_observation(self) -> None:
        content = "University admissions. Applications close on 15 December 2026. Contact office."
        record = self.observe(content)
        quote = "Applications close on 15 December 2026."
        result = self.capture(record, quote)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["matching_occurrences"], 1)
        self.assertEqual(result["span_start"], content.index(quote))
        self.assertEqual(result["span_end"], result["span_start"] + len(quote))
        source = observation_text(self.store, record["id"])
        self.assertEqual(source["visible_text"][result["span_start"]:result["span_end"]],
                         result["exact_quote"])
        self.assertEqual(result["source_text_sha256"], source["visible_text_sha256"])
        self.assertEqual(source_claims(self.store)[0]["span_start"], result["span_start"])
        self.assertEqual(result["verification"], "source_quote_observed_not_fact_verified")

    def test_repeated_quotations_are_not_attributed_to_a_fabricated_unique_span(self) -> None:
        quote = "Applications close on 15 December 2026."
        record = self.observe(quote + " Notices: " + quote + " Read carefully.")
        result = self.capture(record, quote)
        self.assertEqual(result["matching_occurrences"], 2)
        self.assertIsNone(result["span_start"])
        self.assertIsNone(result["span_end"])
        self.assertEqual(source_claims(self.store)[0]["matching_occurrences"], 2)

    def test_old_source_claim_rows_migrate_without_fabricated_text_spans(self) -> None:
        oldpath = self.path.with_name("old.sqlite3")
        conn = sqlite3.connect(oldpath)
        conn.execute(
            "CREATE TABLE source_claims("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,observation_id INTEGER NOT NULL,"
            "application_id TEXT NOT NULL,source_url TEXT NOT NULL,source_digest TEXT NOT NULL,"
            "claim_type TEXT NOT NULL,exact_quote TEXT NOT NULL,candidate_value TEXT NOT NULL,"
            "quote_digest TEXT NOT NULL,captured_at TEXT NOT NULL,"
            "verification TEXT NOT NULL DEFAULT 'source_quote_observed_not_fact_verified',"
            "UNIQUE(observation_id,quote_digest,claim_type,candidate_value))"
        )
        conn.execute(
            "INSERT INTO source_claims(observation_id,application_id,source_url,source_digest,"
            "claim_type,exact_quote,candidate_value,quote_digest,captured_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (12, "APP1", self.url, "a" * 64, "deadline",
             "Applications close on 15 December 2026.", "2026-12-15",
             "b" * 64, "2026-11-10T00:00:00Z"),
        )
        conn.commit()
        conn.close()
        migrated = Store(oldpath)
        try:
            historical = source_claims(migrated)
            self.assertEqual(len(historical), 1)
            self.assertEqual(historical[0]["schema_version"], 2)
            self.assertIsNone(historical[0]["span_start"])
            self.assertIsNone(historical[0]["source_text_sha256"])
            self.assertIsNone(historical[0]["matching_occurrences"])
        finally:
            migrated.close()


if __name__ == "__main__":
    unittest.main()
