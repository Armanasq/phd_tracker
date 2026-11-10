from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from phd_agents.server import ApiServer
from phd_agents.source_claims import capture_source_claim, review_source_claim
from phd_agents.source_conflicts import source_claim_disagreements
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text
from phd_agents.store import Store


class SourceDisagreementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state.sqlite3")
        self.addCleanup(self.store.close)

    def add_claim(self, url: str, date_value: str, app: str = "APP1") -> dict:
        phrase = f"Applications close on {date_value} according to this university programme."
        raw = phrase.encode("utf-8")
        observed = observe_record(
            self.store, app, url,
            fetcher=lambda _: {
                "status": "fetched", "http_status": 200,
                "content_length": len(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(),
                **extract_visible_text(raw, "text/plain"),
            },
        )
        return capture_source_claim(
            self.store, observation_id=observed["id"],
            claim_type="deadline", quote=phrase,
            candidate_value=date_value,
            expected_digest=observed["content_sha256"],
        )

    def test_cross_source_disagreement_remains_unverified(self) -> None:
        first = self.add_claim("https://uni.example/program", "2026-12-15")
        second = self.add_claim("https://department.example/program", "2026-12-20")
        report = source_claim_disagreements(self.store)
        self.assertEqual(report["conflict_count"], 1)
        dispute = report["conflicts"][0]
        self.assertEqual(dispute["source_pattern"], "cross_source_candidate_disagreement")
        self.assertEqual(dispute["distinct_candidate_values"], 2)
        self.assertEqual(dispute["claim_count"], 2)
        self.assertEqual({c["claim_id"] for c in dispute["claims"]}, {first["id"], second["id"]})
        self.assertFalse(dispute["semantic_claim_verified"])
        self.assertEqual(self.store.list_applications(), {})

    def test_historical_version_change_and_owner_rejection_remain_inspectable(self) -> None:
        old = self.add_claim("https://uni.example/program", "2026-12-15")
        latest = self.add_claim("https://uni.example/program", "2026-12-20")
        review_source_claim(
            self.store, claim_id=old["id"],
            expected_source_digest=old["source_digest"],
            expected_quote_digest=old["quote_digest"],
            decision="owner_interpretation_rejected",
            rationale="The old value belongs to a prior programme round and is no longer applicable.",
        )
        report = source_claim_disagreements(self.store)
        self.assertEqual(report["conflicts"][0]["source_pattern"], "same_source_versions_disagree")
        self.assertEqual(report["conflicts"][0]["claims"][1]["owner_review_decision"],
                         "owner_interpretation_rejected")
        self.assertEqual(report["conflicts"][0]["claims"][0]["claim_id"], latest["id"])
        self.assertEqual(report["conflicts"][0]["status"], "manual_disagreement_review_required")

    def test_cross_application_values_are_never_falsely_merged(self) -> None:
        self.add_claim("https://uni.example/doctoral", "2026-12-15", "APP1")
        self.add_claim("https://uni.example/doctoral", "2026-12-20", "APP2")
        self.assertEqual(source_claim_disagreements(self.store)["conflict_count"], 0)

    def test_partial_sample_and_error_inputs(self) -> None:
        self.add_claim("https://uni.example/program", "2026-12-15")
        self.add_claim("https://uni.example/program", "2026-12-20")
        report = source_claim_disagreements(self.store, limit=1)
        self.assertTrue(report["sample_truncated"])
        self.assertEqual(report["conflict_count"], 0)
        for invalid in (0, True, -1, 1001, "500"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                source_claim_disagreements(self.store, limit=invalid)

    def test_private_http_contract(self) -> None:
        self.add_claim("https://uni.example/program", "2026-12-15")
        self.add_claim("https://department.example/program", "2026-12-20")
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/source-claims/conflicts", timeout=5) as response:
                self.assertEqual(response.status, 200)
                data = json.load(response)
            self.assertEqual(data["conflict_count"], 1)
            self.assertFalse(data["semantic_claim_verified"])
            self.assertEqual(data["scope"], "private_owner_candidate_disagreements")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
