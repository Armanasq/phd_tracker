from __future__ import annotations

import unittest
from datetime import date

from phd_agents.proof_queue import evidence_work_queue


class EvidenceWorkQueueTests(unittest.TestCase):
    def test_only_open_tracked_records_create_proof_obligations(self) -> None:
        records = [
            {"id":"A1","name":"Test A","record_type":"tracked","status":"preparing",
             "deadline":"2026-11-12","verification":"unverified","document_states":{"cv":"unknown"}},
            {"id":"A2","name":"Test B","record_type":"candidate","status":"preparing","deadline":"2026-11-12"},
            {"id":"A3","name":"Test C","record_type":"tracked","status":"submitted","receipt":"verified owner receipt"},
        ]
        response=evidence_work_queue(records, [], [], [], date(2026,11,9))
        self.assertTrue(response["items"])
        self.assertEqual({x["application_id"] for x in response["items"]},{"A1"})
        kinds={x["kind"] for x in response["items"]}
        self.assertIn("cutoff_time",kinds)
        self.assertIn("documents",kinds)
        self.assertIn("primary_source",kinds)
        self.assertNotIn("receipt",kinds)
        self.assertEqual(response["items"][0]["days_to_recorded_deadline"],3)
        self.assertIn("heuristic",response["caution"].lower())

    def test_verified_cutoff_suppresses_only_its_task(self) -> None:
        record={"id":"A1","name":"A1","record_type":"tracked","status":"preparing",
                "deadline":"2026-12-01","verification":"source_verified",
                "document_states":{}}
        event={"application_id":"A1","kind":"final","date":"2026-12-01",
               "time":"23:59","timezone":"Europe/London","source_url":"https://university.example/deadline",
               "verification":"primary_confirmed"}
        result=evidence_work_queue([record],[event],[],[],date(2026,11,9))
        self.assertNotIn("cutoff_time",{x["kind"] for x in result["items"]})

    def test_source_conflict_is_flagged_not_resolved(self) -> None:
        record={"id":"A1","name":"A1","record_type":"tracked","status":"preparing",
                "deadline":None,"verification":"unverified"}
        claims=[
            {"id":"C1","application_id":"A1","field":"funding","assertion":"Fully funded","status":"unverified"},
            {"id":"C2","application_id":"A1","field":"funding","assertion":"Tuition only","status":"unverified"},
        ]
        result=evidence_work_queue([record],[],[],claims,date(2026,11,9))
        matches=[x for x in result["items"] if x["kind"]=="evidence_conflict"]
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]["target_section"],"evidence")

    def test_limit_is_enforced(self) -> None:
        record={"id":"A1","record_type":"tracked","status":"preparing","deadline":None}
        result=evidence_work_queue([record],[],[],[],date(2026,11,9),limit=1)
        self.assertEqual(len(result["items"]),1)
        self.assertGreater(result["total"],1)
        with self.assertRaises(ValueError):
            evidence_work_queue([record],[],[],[],date(2026,11,9),limit=0)


if __name__=="__main__":
    unittest.main()
