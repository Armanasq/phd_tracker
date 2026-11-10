from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from phd_agents.source_changes import compare_sources, load_snapshot


class SourceChangeProvenanceTests(unittest.TestCase):
    def test_changed_deadline_creates_deterministic_manual_review_event(self) -> None:
        prior = {"as_of": "2026-11-08", "records": [
            {"id": "A", "deadline": "2026-11-20", "verification": "source_verified",
             "source_url": "https://university.example.edu/apply?token=sensitive"},
        ]}
        latest = {"as_of": "2026-11-10", "records": [
            {"id": "A", "deadline": "2026-11-23", "verification": "source_verified",
             "source_url": "https://university.example.edu/apply?token=sensitive"},
        ]}
        result = compare_sources(prior, latest, today=date(2026, 11, 10))
        self.assertEqual(result["changed_items"], 1)
        change = result["changes"][0]
        self.assertEqual(change["field"], "deadline")
        self.assertEqual(change["review_status"], "needs_primary_recheck")
        self.assertNotIn("token=sensitive", json.dumps(result))
        self.assertEqual(change["before"], '"2026-11-20"')
        self.assertEqual(change["after"], '"2026-11-23"')
        self.assertEqual(change["event_id"], compare_sources(prior, latest, today=date(2026, 11, 10))["changes"][0]["event_id"])

    def test_disappearing_candidate_is_not_treated_as_closed(self) -> None:
        prior = {"records": [{"id": "A", "source_url": "https://lab.example.edu/apply"}]}
        current = {"records": []}
        result = compare_sources(prior, current, today=date(2026, 11, 10))
        self.assertEqual(result["changes"][0]["kind"], "record_missing_from_new_snapshot")
        self.assertTrue(result["changes"][0]["requires_review"])
        self.assertNotIn("confirmed_closed", json.dumps(result))

    def test_stale_observation_is_not_live_source_verification(self) -> None:
        old = {"records": []}
        recent = {"as_of": "2026-10-01", "records": [
            {"id": "A", "deadline": "2026-11-20", "source_url": "http://127.0.0.1/metadata"},
        ]}
        result = compare_sources(old, recent, today=date(2026, 11, 10))
        self.assertEqual(result["snapshot_freshness"], "stale_snapshot")
        self.assertEqual(result["changes"][0]["review_status"], "missing_primary_source")
        self.assertEqual(result["current_snapshot_age_days"], 40)

    def test_invalid_duplicate_and_oversized_records_fail_closed(self) -> None:
        good = {"records": []}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compare_sources({"records": [{"id": "A"}, {"id": "A"}]}, good)
        with self.assertRaisesRegex(ValueError, "records array"):
            compare_sources({}, good)
        with self.assertRaisesRegex(ValueError, "freshness"):
            compare_sources(good, good, freshness_days=0)

    def test_file_loader_rejects_symlinks_and_non_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / "previous.json"
            sample.write_text(json.dumps({"records": []}), encoding="utf-8")
            self.assertEqual(load_snapshot(sample), {"records": []})
            shortcut = root / "alias.json"
            shortcut.symlink_to(sample)
            with self.assertRaisesRegex(ValueError, "ordinary local JSON"):
                load_snapshot(shortcut)
            sample.write_text("[1,2]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_snapshot(sample)


if __name__ == "__main__":
    unittest.main()
