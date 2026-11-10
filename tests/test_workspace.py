from __future__ import annotations

import json
import re
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
        ids = [row["id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(value["meta"]["tracked"], sum(row["record_type"] == "tracked" for row in rows))
        self.assertEqual(value["meta"]["candidates"], sum(row["record_type"] == "candidate" for row in rows))
        self.assertEqual(value["meta"]["tracked"] + value["meta"]["candidates"], len(rows))
        self.assertTrue(all(row["status"] in {"unconfirmed", "shortlisted", "preparing", "submitted", "interview", "offer", "rejected", "withdrawn", "blocked", "archived"} for row in rows))
        self.assertTrue(all("mail.google.com" not in json.dumps(row) for row in rows))
        self.assertTrue(all("@" not in row["faculty"] for row in rows))
        if value["instance"]["data_mode"] == "starter":
            self.assertEqual(rows, [])
        elif value["instance"]["type"] == "upstream":
            self.assertTrue(rows)
            self.assertTrue(any("unknown" in row["document_states"].values() for row in rows))

    def test_coverage_reports_source_grain_without_invented_opportunities(self):
        snapshot = build()
        coverage = snapshot["coverage"]
        self.assertEqual(coverage["totals"]["tracked"], snapshot["meta"]["tracked"])
        self.assertEqual(coverage["totals"]["research_candidates"], snapshot["meta"]["candidates"])
        if snapshot["instance"]["type"] == "upstream" and snapshot["instance"]["data_mode"] == "source":
            self.assertGreaterEqual(coverage["totals"]["workbook_tabs"], 1)
            self.assertTrue(any(sheet["name"] == "Action list" for sheet in coverage["worksheets"]))
        else:
            self.assertEqual(coverage["worksheets"], [])
            self.assertEqual(coverage["totals"]["workbook_tabs"], 0)
        self.assertTrue(all(item["path"] == "PhD_Action_List.xlsx" or item["path"].startswith("data/") for item in coverage["files"]))
        self.assertFalse(any("mail.google.com" in json.dumps(item) for item in coverage["files"]))

    def test_full_task_ledger_is_source_faithful_and_public_safe(self):
        snapshot = build()
        ledger = snapshot["task_ledger"]
        if snapshot["instance"]["type"] == "upstream" and snapshot["instance"]["data_mode"] == "source":
            source = json.loads((Path(__file__).resolve().parents[1] / "data" / "execution_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger), len(source["all_tasks"]))
        else:
            self.assertEqual(ledger, [])
        self.assertEqual(snapshot["coverage"]["totals"]["full_task_ledger"], len(ledger))
        self.assertEqual(len({item["id"] for item in ledger}), len(ledger))
        self.assertTrue(all("mail.google.com" not in json.dumps(item) for item in ledger))
        self.assertTrue(all(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+[.][A-Z]{2,}", item["action"], re.I) is None for item in ledger))

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

    def test_private_notes_cannot_be_committed_from_public_issue(self):
        previous = {"schema_version": 1, "records": {}, "processed_comment_ids": []}
        event = {"action": "created", "issue": {"body": "<!-- phd-intelligence-action-center-v1 -->"}, "comment": {"id": 444, "user": {"login": "Armanasq"}, "body": '/workspace {"id":"N263-05","notes":"Private note","status":"preparing"}'}}
        unchanged, result = transform(event, "Armanasq", {"N263-05"}, previous)
        self.assertFalse(result["accepted"])
        self.assertEqual(unchanged, previous)


    def test_version_checked_updates_reject_stale_source(self):
        previous = {"schema_version":1, "records":{"N263-05":{"status":"shortlisted","updated_at":"2026-11-09T10:00:00+00:00"}}, "processed_comment_ids":[]}
        event = {"action":"created","issue":{"body":"<!-- phd-intelligence-action-center-v1 -->"},"comment":{"id":677,"user":{"login":"Armanasq"},"body":'/workspace {"id":"N263-05","expected_updated_at":"2026-11-08T10:00:00+00:00","status":"preparing"}'}}
        unchanged, result=transform(event,"Armanasq",{"N263-05"},previous)
        self.assertFalse(result["accepted"])
        self.assertIn("source_version_conflict",result["reason"])
        self.assertEqual(unchanged,previous)
        event["comment"]["body"]='/workspace {"id":"N263-05","expected_updated_at":"2026-11-09T10:00:00+00:00","priority":"high","status":"preparing"}'
        changed,accepted=transform(event,"Armanasq",{"N263-05"},previous)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(changed["records"]["N263-05"]["priority"],"high")

    def test_verified_candidate_promotion_and_sensitive_data_rejection(self):
        previous={"schema_version":1,"records":{},"processed_comment_ids":[]}
        event={"action":"created","issue":{"body":"<!-- phd-intelligence-action-center-v1 -->"},"comment":{"id":781,"user":{"login":"Armanasq"},"body":'/workspace {"id":"N263-05","promoted":true,"expected_updated_at":""}'}}
        same,denied=transform(event,"Armanasq",{"N263-05"},previous)
        self.assertFalse(denied["accepted"])
        event["comment"]["body"]='/workspace {"id":"N263-05","promoted":true,"verification":"source_verified","expected_updated_at":""}'
        updated,accepted=transform(event,"Armanasq",{"N263-05"},previous)
        self.assertTrue(accepted["accepted"])
        self.assertTrue(updated["records"]["N263-05"]["promoted"])
        event["comment"]["body"]='/workspace {"id":"N263-05","notes":"private"}'
        same,denied=transform(event,"Armanasq",{"N263-05"},previous)
        self.assertFalse(denied["accepted"])
        self.assertEqual(same,previous)



if __name__ == "__main__":
    unittest.main()
