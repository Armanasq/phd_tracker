from __future__ import annotations

import json
import unittest

from phd_agents.evidence_pack import bounded_evidence


class BoundedEvidenceTests(unittest.TestCase):
    def test_small_evidence_round_trips_exactly(self):
        payload={"record":{"id":"A1","name":"Test"},"status":"unknown"}
        self.assertEqual(json.loads(bounded_evidence(payload)),payload)

    def test_extremely_large_evidence_is_valid_and_bounded(self):
        payload={"record":{"id":"A1","name":"Test","notes":"Z"*60000},
                 "tool_results":{"tools":[{"content":"A"*100000} for _ in range(100)]},
                 "proof_queue":[{"action":"Review deadline","proof_needed":"Official source"}]*1000}
        for budget in (1200,4000,15000):
            response=bounded_evidence(payload,max_chars=budget)
            self.assertLessEqual(len(response),budget)
            decoded=json.loads(response)
            self.assertTrue(decoded["_evidence_truncated"])
            self.assertNotIn("password",response.lower())

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            bounded_evidence({},max_chars=100)
        with self.assertRaises(ValueError):
            bounded_evidence([],max_chars=5000)


if __name__=="__main__":
    unittest.main()
