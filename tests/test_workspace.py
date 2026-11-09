from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_workspace import build, duplicate_advisories, public_url
from workspace_controls import transform


class WorkspaceTests(unittest.TestCase):
    def test_projection_preserves_ids_and_explicit_unknowns(self):
        value = build()
        rows = value["records"]
        self.assertGreaterEqual(len(rows), 109)
        ids = [row["id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(value["meta"]["tracked"], 109)
        self.assertTrue(all(row["status"] in {"unconfirmed", "shortlisted", "preparing", "submitted", "interview", "offer", "rejected", "withdrawn", "blocked", "archived"} for row in rows))
        self.assertTrue(any("unknown" in row["document_states"].values() for row in rows))
        self.assertTrue(all("mail.google.com" not in json.dumps(row) for row in rows))
        self.assertTrue(all("@" not in row["faculty"] for row in rows))

    def test_url_filters_mailbox_links(self):
        self.assertEqual(public_url("https://mail.google.com/mail/u/0/#all/123"), "")
        self.assertEqual(public_url("javascript:alert(1)"), "")
        self.assertTrue(public_url("https://www.ucl.ac.uk/"))

    def test_duplicates_not_promoted(self):
        data = [
            {"id":"one", "name":"Same university robotics PhD", "source_url":"https://a.example"},
            {"id":"two", "name":"Same university robotics PhD", "source_url":"https://a.example"},
        ]
        matches = duplicate_advisories(data)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["certainty"], "possible_duplicate_not_confirmed")

    def test_owner_only_comment_and_validated_fields(self):
        previous = {"schema_version": 1, "records":{}, "processed_comment_ids":[]}
        event = {"action":"created", "issue":{"body":"<!-- phd-intelligence-action-center-v1 -->"}, "comment":{"id": 123, "user":{"login":"Armanasq"}, "body":'/workspace {"id":"N263-05","status":"shortlisted","documents":{"academic_cv":"ready"}}'}}
        unchanged, denied = transform(event, "SomeoneElse", {"N263-05"}, previous)
        self.assertFalse(denied["accepted"])
        self.assertEqual(unchanged, previous)
        modified, accepted = transform(event, "Armanasq", {"N263-05"}, previous)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(modified["records"]["N263-05"]["status"], "shortlisted")
        replay, denied = transform(event, "Armanasq", {"N263-05"}, modified)
        self.assertFalse(denied["accepted"])
        self.assertEqual(replay, modified)


if __name__ == "__main__":
    unittest.main()
