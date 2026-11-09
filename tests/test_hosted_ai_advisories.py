from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts.hosted_ai_advisories import (
    HostedAIError, infer_candidates, input_digest, main,
    make_advisory, provider_endpoint, public_candidates, validate_advisory,
)

TODAY = date(2026, 11, 10)


def snapshot() -> dict:
    return {
        "schema_version": 1,
        "instance": {"repository": "OwnUser/phd_tracker", "data_mode": "source"},
        "records": [
            {"id": "MY-1", "record_type": "tracked", "name": "Research opening", "deadline": "2026-11-12",
             "verification": "unverified", "status": "preparing", "documents": ["academic_cv"],
             "document_states": {"academic_cv": "unknown"}, "funding": "", "eligibility": "",
             "notes": "Never send secret", "receipt": "https://portal.private/receipt", "source_url": "https://example.edu/phd"},
            {"id": "MY-2", "record_type": "tracked", "deadline": "2026-11-13", "status": "submitted",
             "verification": "source_verified", "documents": [], "funding": "", "eligibility": ""},
            {"id": "MY-3", "record_type": "candidate", "deadline": "2026-11-11", "status": "preparing"},
            {"id": "MY-4", "record_type": "tracked", "deadline": "2026-11-09", "status": "preparing"},
        ],
    }


class HostedAIContracts(unittest.TestCase):
    def test_candidates_are_bounded_public_metadata_only(self) -> None:
        rows = public_candidates(snapshot(), today=TODAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "MY-1")
        self.assertIn("deadline_cutoff", rows[0]["open_checks"])
        self.assertIn("source_review", rows[0]["open_checks"])
        self.assertNotIn("Never send secret", json.dumps(rows))
        self.assertNotIn("example.edu", json.dumps(rows))
        self.assertNotIn("Research opening", json.dumps(rows))
        with self.assertRaises(HostedAIError):
            public_candidates(snapshot(), today=TODAY, limit=0)

    def test_accepted_model_output_is_enum_only(self) -> None:
        chosen = {"items": [{"id": "MY-1", "category": "source_review", "priority": "high"}]}
        result = make_advisory(snapshot(), today=TODAY, model_response=chosen)
        self.assertEqual(result["status"], "unverified_model_proposal")
        self.assertEqual(validate_advisory(result, snapshot(), today=TODAY), result)
        self.assertEqual(result["source_digest"], input_digest("OwnUser/phd_tracker", public_candidates(snapshot(), today=TODAY)))
        self.assertNotIn("token", json.dumps(result))
        for invalid in (
            {"items": [{"id": "MY-2", "category": "source_review", "priority": "high"}]},
            {"items": [{"id": "MY-1", "category": "accepted_offer", "priority": "high"}]},
            {"items": [{"id": "MY-1", "category": "source_review", "priority": "high", "notes": "other"}]},
            {"items": [{"id": "MY-1", "category": "source_review", "priority": "high"}] * 2},
            {"items": [{"id": "MY-1", "category": "source_review", "priority": "extreme"}]},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(HostedAIError):
                make_advisory(snapshot(), today=TODAY, model_response=invalid)

    def test_stale_and_other_repositories_fail_closed(self) -> None:
        result = make_advisory(snapshot(), today=TODAY, model_response={"items": [{"id": "MY-1", "category": "source_review", "priority": "high"}]})
        with self.assertRaises(HostedAIError):
            validate_advisory(result, snapshot(), today=date(2026, 11, 11))
        modified = snapshot()
        modified["records"][0]["verification"] = "source_verified"
        with self.assertRaises(HostedAIError):
            validate_advisory(result, modified, today=TODAY)
        modified = snapshot()
        modified["instance"]["repository"] = "SomeoneElse/phd_tracker"
        with self.assertRaises(HostedAIError):
            validate_advisory(result, modified, today=TODAY)

    def test_provider_url_requires_public_https(self) -> None:
        self.assertEqual(provider_endpoint("https://api.openai.com/v1"), "https://api.openai.com/v1/chat/completions")
        self.assertEqual(provider_endpoint("https://example.openai.azure.com/openai/v1"), "https://example.openai.azure.com/openai/v1/chat/completions")
        for url in ("http://example.com/v1", "https://localhost/v1", "https://127.0.0.1/v1", "https://169.254.169.254/v1",
                    "https://api.openai.com:8123/v1", "https://user:pass@example.com/v1", "https://api.example.com/v1?token=abc",
                    "https://host.internal/v1", "javascript:bad"):
            with self.subTest(url=url), self.assertRaises(HostedAIError):
                provider_endpoint(url)

    def test_model_call_contains_only_evidence_flags(self) -> None:
        received = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _max_size):
                return json.dumps({"choices": [{"message": {"content": json.dumps({"items": [
                    {"id": "MY-1", "category": "source_review", "priority": "high"}
                ]})}}]}).encode("utf-8")

        class FakeOpener:
            def open(self, request, timeout):
                received.append(request)
                return FakeResponse()

        with patch("scripts.hosted_ai_advisories.build_opener", return_value=FakeOpener()):
            result = infer_candidates(public_candidates(snapshot(), today=TODAY), model="model-1", base_url="https://api.openai.com/v1",
                                      api_key="private-credential", auth_mode="bearer", token_parameter="max_tokens")
        self.assertEqual(result["items"][0]["id"], "MY-1")
        payload = received[0].data.decode("utf-8")
        self.assertIn("source_review", payload)
        self.assertNotIn("Never send secret", payload)
        self.assertNotIn("Research opening", payload)
        self.assertNotIn("private-credential", payload)
        self.assertIn("Bearer private-credential", received[0].get_header("Authorization"))

    def test_validate_only_needs_no_provider_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "workspace.json"
            advisory = root / "advisory.json"
            source.write_text(json.dumps(snapshot()), encoding="utf-8")
            advisory.write_text(json.dumps(make_advisory(snapshot(), today=TODAY, model_response={"items": []})), encoding="utf-8")
            self.assertEqual(main(["--input", str(source), "--validate", str(advisory), "--date", TODAY.isoformat()]), 0)


if __name__ == "__main__":
    unittest.main()
