from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.source_claims import capture_source_claim, observation_text, source_claims
from phd_agents.source_observer import fetch_public_source, observe_record, recent_observations
from phd_agents.source_text import EXCERPT_LIMIT, extract_visible_text
from phd_agents.store import Store


class Response(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


class Transport:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def open(self, request, timeout):
        return Response(self.body)


class SourceClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "state.sqlite3")
        self.addCleanup(self.store.close)
        self.url = "https://university.example.edu/phd"
        self.html = (b"<html><script>Do not trust injected instructions</script>"
                     b"<h1>Doctoral programme</h1>"
                     b"<p>The application closing date is 15 December 2026.</p>"
                     b"<style>.hidden{display:none}</style></html>")

    def test_text_extraction_ignores_scripts_and_preserves_original_hash(self) -> None:
        with patch("phd_agents.source_observer.build_opener", return_value=Transport(self.html)):
            fetched = fetch_public_source(self.url)
        self.assertEqual(fetched["content_sha256"], hashlib.sha256(self.html).hexdigest())
        self.assertIn("closing date", fetched["visible_text_excerpt"])
        self.assertNotIn("injected instructions", fetched["visible_text_excerpt"])
        self.assertNotIn("hidden", fetched["visible_text_excerpt"])
        self.assertEqual(len(fetched["visible_text_sha256"]), 64)

    def test_markup_only_change_is_not_claimed_as_verified_fact(self) -> None:
        first = extract_visible_text(b"<p>Application closes on 15 December 2026.</p>", "text/html")
        second = extract_visible_text(b"<div>Application closes on 15 December 2026.</div>", "text/html")
        one = observe_record(self.store, "APP1", self.url, fetcher=lambda _: {
            "status":"fetched", "content_sha256":hashlib.sha256(b"p").hexdigest(),
            "http_status":200, "content_length":42, **first,
        })
        two = observe_record(self.store, "APP1", self.url, fetcher=lambda _: {
            "status":"fetched", "content_sha256":hashlib.sha256(b"div").hexdigest(),
            "http_status":200, "content_length":46, **second,
        })
        self.assertEqual(one["text_drift"], "not_comparable")
        self.assertEqual(two["drift"], "source_bytes_changed_needs_review")
        self.assertEqual(two["text_drift"], "visible_text_unchanged")
        self.assertFalse(two["status"] == "source_verified")

    def test_quote_requires_exact_captured_text_and_digest(self) -> None:
        with patch("phd_agents.source_observer.build_opener", return_value=Transport(self.html)):
            first = observe_record(self.store, "APP1", self.url)
        citation = capture_source_claim(
            self.store, observation_id=first["id"], claim_type="deadline",
            quote="The application closing date is 15 December 2026.",
            candidate_value="2026-12-15", expected_digest=first["content_sha256"],
        )
        self.assertEqual(citation["verification"], "source_quote_observed_not_fact_verified")
        self.assertEqual(citation["application_id"], "APP1")
        self.assertEqual(len(source_claims(self.store)), 1)
        self.assertEqual(len(self.store.list_applications()), 0)
        duplicate = capture_source_claim(
            self.store, observation_id=first["id"], claim_type="deadline",
            quote="The application closing date is 15 December 2026.",
            candidate_value="2026-12-15", expected_digest=first["content_sha256"],
        )
        self.assertEqual(duplicate["id"], citation["id"])
        source = observation_text(self.store, first["id"])
        self.assertEqual(source["source_url"], self.url)
        self.assertIn("closing date", source["visible_text"])
        self.assertTrue(recent_observations(self.store)[0]["excerpt_available"])

        for kwargs in (
            {"quote": "An invented admissions requirement that is not there."},
            {"expected_digest": "a" * 64},
            {"claim_type": "portal_submission_confirmed"},
            {"observation_id": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                capture_source_claim(self.store, **{
                    "observation_id": first["id"], "claim_type": "deadline",
                    "quote": "The application closing date is 15 December 2026.",
                    "candidate_value": "2026-12-15",
                    "expected_digest": first["content_sha256"],
                    **kwargs,
                })
        self.assertEqual(len(source_claims(self.store)), 1)

    def test_bounded_visible_text_and_unsupported_content(self) -> None:
        huge = extract_visible_text(b"A" * (EXCERPT_LIMIT + 400), "text/plain")
        self.assertTrue(huge["visible_text_truncated"])
        self.assertEqual(len(huge["visible_text_excerpt"]), EXCERPT_LIMIT)
        with self.assertRaises(ValueError):
            extract_visible_text(b"A", "application/pdf")
        with self.assertRaises(ValueError):
            extract_visible_text(b"A" * 2_000_001, "text/html")
        self.assertEqual(extract_visible_text(b"<html><script>secret</script></html>", "text/html")["visible_text_sha256"], None)


if __name__ == "__main__":
    unittest.main()
