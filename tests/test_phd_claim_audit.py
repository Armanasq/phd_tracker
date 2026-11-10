from __future__ import annotations

import json
import unittest

from phd_agents.claim_audit import audit_generated_claims


class ClaimAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = [{"application_id": "APP01", "verification": "source_verified",
                         "source_url": "https://university.example.edu/doctoral"}]
        self.claims = [{"id": "EV1", "application_id": "APP01",
                        "status": "primary_confirmed", "source_url": "https://university.example.edu/doctoral",
                        "excerpt": "Original source wording", "assertion": "Original assertion"}]

    def test_links_only_to_provided_evidence_not_semantic_claim_verification(self) -> None:
        response = (
            "Deadline recorded for the programme. [source:APP01]\n"
            "The published offer has funding. [claim:EV1]\n"
            "Further eligibility is unknown."
        )
        result = audit_generated_claims(response, self.sources, self.claims)
        self.assertEqual(result["linked_to_reviewed_records"], 2)
        self.assertEqual(result["unlinked_text_blocks"], 1)
        self.assertEqual(result["unknown_reference_links"], 0)
        self.assertFalse(result["semantic_entailment_verified"])
        self.assertEqual(result["status"], "requires_human_fact_check")
        self.assertNotIn("Original source wording", json.dumps(result))

    def test_nonexistent_or_unverified_sources_never_count_as_reviewed(self) -> None:
        unverified = [dict(self.sources[0], verification="unverified", source_url="http://invalid.local")]
        claims = [dict(self.claims[0], excerpt="")]
        report = audit_generated_claims(
            "Claim A [source:APP01]\nClaim B [claim:EV1]\nClaim C [source:DOES_NOT_EXIST]",
            unverified, claims,
        )
        self.assertEqual(report["linked_to_reviewed_records"], 0)
        self.assertEqual(report["linked_to_unverified_records"], 2)
        self.assertEqual(report["unknown_reference_links"], 1)
        self.assertEqual(report["unlinked_text_blocks"], 0)

    def test_prompt_and_secret_contents_are_never_reproduced(self) -> None:
        data = audit_generated_claims(
            "SENSITIVE_PERSONAL_PROMPT\nPrivate key SECRET0000", [], []
        )
        text = json.dumps(data)
        self.assertNotIn("SENSITIVE", text)
        self.assertNotIn("SECRET", text)
        self.assertEqual(data["unlinked_text_blocks"], 2)

    def test_invalid_payload_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            audit_generated_claims("A" * 20001, [], [])
        with self.assertRaises(ValueError):
            audit_generated_claims("text", None, [])


if __name__ == "__main__":
    unittest.main()
