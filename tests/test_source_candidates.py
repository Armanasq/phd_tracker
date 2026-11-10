from __future__ import annotations

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import json

from phd_agents.server import ApiServer
from phd_agents.source_candidates import extract_date_candidates, source_date_candidates
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text, normalize_excerpt
from phd_agents.store import Store


class CandidateDateTests(unittest.TestCase):
    def parse(self, text: str, *, truncated: bool = False) -> dict:
        text = normalize_excerpt(text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return extract_date_candidates(
            text, source_url="https://university.example/program",
            application_id="APP1", observed_at="2026-11-10T09:00:00+00:00",
            source_digest=digest, text_digest=digest, source_truncated=truncated,
        )

    def test_multiple_formats_and_no_unverified_promotion(self) -> None:
        text = ("Applications close on 15 December 2026. "
                "The new application deadline is December 20, 2026. "
                "Interviews take place on 2027-01-12.")
        parsed = self.parse(text)
        self.assertEqual([x["normalized_date"] for x in parsed["candidates"]],
                         ["2026-12-15", "2026-12-20", "2027-01-12"])
        self.assertTrue(parsed["ambiguous_deadline_dates"])
        self.assertEqual([item["candidate_type"] for item in parsed["candidates"]],
                         ["deadline", "deadline", "other"])
        self.assertTrue(parsed["scan_complete"])
        self.assertFalse(parsed["semantic_claim_verified"])
        for item in parsed["candidates"]:
            self.assertEqual(text[item["span_start"]:item["span_end"]], item["date_mention"])
            self.assertEqual(item["review_status"], "unverified_candidate_no_auto_promotion")
            self.assertEqual(item["source_location"], "normalized_visible_text_characters")

    def test_invalid_dates_and_locale_ambiguous_numerics_are_not_parsed(self) -> None:
        parsed = self.parse("Deadline 31 February 2026; due 01/02/2026; on 2026-02-29. "
                            "However 2028-02-29 is a legitimate calendar date.")
        self.assertEqual([x["normalized_date"] for x in parsed["candidates"]], ["2028-02-29"])
        self.assertFalse(parsed["ambiguous_deadline_dates"])

    def test_no_deadline_language_means_only_date_mention(self) -> None:
        parsed = self.parse("Publication issued 2026-11-10; event starts on 12 November 2026.")
        self.assertTrue(all(x["candidate_type"] == "other" for x in parsed["candidates"]))
        self.assertEqual(parsed["status"], "review_candidates_only")

    def test_bounded_input_and_truncation_are_explicit(self) -> None:
        repeated = ("Apply by 15 January 2027. " * 60).strip()
        parsed = self.parse(repeated)
        self.assertEqual(parsed["candidate_count"], 25)
        self.assertTrue(parsed["candidate_limit_exceeded"])
        self.assertFalse(parsed["scan_complete"])
        self.assertFalse(self.parse("Apply by 15 January 2027.", truncated=True)["scan_complete"])
        with self.assertRaises(ValueError):
            self.parse("A" * 24001)
        with self.assertRaises(ValueError):
            extract_date_candidates("15 January 2027", source_url="", application_id="X",
                                    observed_at="", source_digest="bad", text_digest="bad")
        with self.assertRaises(ValueError):
            extract_date_candidates("2026-11-10", source_url="", application_id="X",
                                    observed_at="", source_digest="a" * 64,
                                    text_digest="0" * 64)

    def test_explicit_iso_datetime_offsets_are_normalized_without_verifying_deadlines(self) -> None:
        report = self.parse(
            "Applications close 2026-12-15T23:59:00-05:00. "
            "A second round closes 2027-01-12T17:30+01:00. "
            "Interview 2027-02-03T09:00Z."
        )
        self.assertEqual(
            [c["normalized_utc_instant"] for c in report["candidates"]],
            ["2026-12-16T04:59:00Z", "2027-01-12T16:30:00Z", "2027-02-03T09:00:00Z"],
        )
        self.assertEqual(report["candidates"][0]["source_explicit_timestamp"], "2026-12-15T23:59:00-05:00")
        self.assertFalse(report["semantic_claim_verified"])
        self.assertEqual(report["candidates"][2]["candidate_type"], "other")

    def test_offset_free_invalid_and_abbreviated_times_remain_unknown(self) -> None:
        report = self.parse(
            "Deadline 2027-01-15T17:00. "
            "Deadline 2027-02-15T10:30+14:30. "
            "Deadline 2027-03-15 10:30 CET. "
            "Deadline 15 April 2027 at 17:00 UTC. "
            "Deadline 2027-05-15T25:00+01:00."
        )
        self.assertEqual(report["candidate_count"], 5)
        self.assertTrue(all(c["normalized_utc_instant"] is None for c in report["candidates"]))
        self.assertTrue(all(c["source_explicit_timestamp"] is None for c in report["candidates"]))
        self.assertFalse(report["semantic_claim_verified"])

    def test_source_record_api_is_private_and_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            store = Store(root / "data.sqlite3")
            body = "Applications close on 15 December 2026."
            raw = body.encode()
            observed = observe_record(store, "APP1", "https://university.example/program",
                fetcher=lambda _: {"status": "fetched", "http_status": 200,
                                   "content_length": len(raw),
                                   "content_sha256": hashlib.sha256(raw).hexdigest(),
                                   **extract_visible_text(raw, "text/plain")})
            report = source_date_candidates(store, observed["id"])
            self.assertEqual(report["candidate_count"], 1)
            self.assertFalse(report["semantic_claim_verified"])
            server = ApiServer(("127.0.0.1", 0), store=store, root=root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base}/api/source-observations/{observed['id']}/candidates") as response:
                    result = json.load(response)["result"]
                self.assertEqual(result["observation_id"], observed["id"])
                self.assertEqual(result["candidates"][0]["candidate_type"], "deadline")
                with self.assertRaises(HTTPError) as invalid:
                    urlopen(f"{base}/api/source-observations/not-an-int/candidates")
                self.assertEqual(invalid.exception.code, 400)
                self.assertEqual(store.list_applications(), {})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                store.close()


if __name__ == "__main__":
    unittest.main()
