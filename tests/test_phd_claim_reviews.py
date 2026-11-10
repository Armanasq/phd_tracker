from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from phd_agents.source_claims import capture_source_claim, review_source_claim, source_claims, claim_review_history
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text
from phd_agents.store import Store


class ClaimReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "data.sqlite3")
        self.addCleanup(self.store.close)
        self.text = "Doctoral applications close on 15 December 2026."
        raw = self.text.encode("utf-8")
        self.observation = observe_record(
            self.store, "APP1", "https://university.example.edu/phd",
            fetcher=lambda _: {
                "status": "fetched", "http_status": 200, "content_length": len(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(),
                **extract_visible_text(raw, "text/plain"),
            },
        )
        self.claim = capture_source_claim(
            self.store, observation_id=self.observation["id"],
            claim_type="deadline", quote=self.text,
            candidate_value="2026-12-15",
            expected_digest=self.observation["content_sha256"],
        )

    def review(self, **changes) -> dict:
        args = {
            "claim_id": self.claim["id"],
            "expected_source_digest": self.claim["source_digest"],
            "expected_quote_digest": self.claim["quote_digest"],
            "decision": "needs_recheck",
            "rationale": "This is an exact source quote, but portal closing time is missing.",
        }
        args.update(changes)
        return review_source_claim(self.store, **args)

    def test_review_history_append_only_and_never_promotes_application(self) -> None:
        first = self.review()
        duplicate = self.review()
        self.assertFalse(first["reused"])
        self.assertTrue(duplicate["reused"])
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(source_claims(self.store)[0]["owner_review_decision"], "needs_recheck")
        next_review = self.review(
            decision="owner_interpretation_supported",
            rationale="Original institutional quotation inspected manually; date interpretation appears consistent.",
        )
        self.assertFalse(next_review["reused"])
        self.assertEqual(source_claims(self.store)[0]["owner_review_decision"], "owner_interpretation_supported")
        self.assertEqual(source_claims(self.store)[0]["verification"],
                         "source_quote_observed_not_fact_verified")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM source_claim_reviews",
        ).fetchone()[0], 2)
        history = claim_review_history(self.store, claim_id=self.claim["id"])
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["decision"], "owner_interpretation_supported")
        self.assertIn("date interpretation appears consistent", history[0]["rationale"])
        self.assertNotIn("rationale", str(source_claims(self.store)[0]))
        self.assertEqual(self.store.list_applications(), {})

    def test_invalid_id_decision_digests_and_rationale_rejected(self) -> None:
        bad = [
            {"claim_id": True}, {"claim_id": 0}, {"claim_id": 999},
            {"decision": "primary_confirmed"},
            {"expected_source_digest": "0" * 64},
            {"expected_quote_digest": "f" * 64},
            {"rationale": "Short"},
            {"rationale": "<bad>\u0000 text"},
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.review(**item)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM source_claim_reviews",
        ).fetchone()[0], 0)

    def test_history_requires_existing_claim_id(self) -> None:
        for identity in (0, True, 999999):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                claim_review_history(self.store, claim_id=identity)

    def test_duplicate_quote_capture_does_not_inflate_audit_log(self) -> None:
        before = self.store.db.execute(
            "SELECT COUNT(*) FROM audit WHERE action='source:quote_captured'"
        ).fetchone()[0]
        same = capture_source_claim(
            self.store, observation_id=self.observation["id"],
            claim_type="deadline", quote=self.text,
            candidate_value="2026-12-15",
            expected_digest=self.observation["content_sha256"],
        )
        self.assertEqual(same["id"], self.claim["id"])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM audit WHERE action='source:quote_captured'"
        ).fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
