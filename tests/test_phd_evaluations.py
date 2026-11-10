from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from phd_agents.evaluations import evaluation_report
from phd_agents.server import ApiServer
from phd_agents.store import Store


class EvaluationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "owner.sqlite3")
        self.addCleanup(self.store.close)
        self.root = Path(temp.name)

    def write(self, *, agent: str, provider: str, status: str = "proposed",
              kind: str = "agent", payload: dict | None = None) -> str:
        return self.store.put_run(kind, agent, "APPLICATION_PRIVATE", status, provider, payload or {})

    def test_empty_report_preserves_unknown_measures(self) -> None:
        report = evaluation_report(self.store)
        self.assertEqual(report["status"], "no_observations")
        self.assertEqual(report["summary"]["calls"], 0)
        self.assertIsNone(report["summary"]["failure_rate"])
        self.assertIsNone(report["summary"]["latency_p95_ms"])
        self.assertFalse(report["summary"]["semantic_entailment_verified"])

    def test_run_groups_and_citation_audits_do_not_expose_private_text(self) -> None:
        self.write(agent="deadline_auditor", provider="ollama", payload={
            "text": "PRIVATE APPLICANT DETAIL: transcript",
            "model": "model-a", "prompt_contract_id": "phd_evidence_analysis_v1",
            "latency_ms": 500, "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            "claim_audit": {"schema_version": 1, "unknown_reference_links": 2,
                            "linked_to_unverified_records": 1,
                            "linked_to_reviewed_records": 1, "unlinked_text_blocks": 3},
        })
        self.write(agent="deadline_auditor", provider="ollama", status="failed",
                   payload={"error_type": "TimeoutError", "secret": "SYNTHETIC_API_KEY"})
        self.write(agent="research_fit", provider="openai", payload={
            "text": "PRIVATE RESEARCH NOTE", "latency_ms": 1500, "usage": {},
        })
        self.write(agent="flow", provider="multi_route", kind="workflow_summary", payload={
            "stage_count": 2, "completed_run_ids": ["a", "b"], "notice": "INTERNAL PROMPT",
        })
        report = evaluation_report(self.store)
        self.assertEqual(report["sampled_runs"], 3)
        self.assertEqual(report["summary"]["calls"], 3)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["summary"]["failure_rate"], 0.3333)
        self.assertEqual(report["summary"]["citation_audits"], 1)
        self.assertEqual(report["summary"]["unknown_reference_links"], 2)
        self.assertEqual(report["summary"]["unverified_reference_links"], 1)
        self.assertEqual(report["summary"]["latency_p95_ms"], 1500)
        self.assertEqual(report["summary"]["usage_reported"], 1)
        self.assertEqual(report["providers"][0]["provider_id"], "ollama")
        self.assertEqual(len(report["workflow_summaries"]), 1)
        serialized = json.dumps(report)
        for prohibited in ("PRIVATE", "SYNTHETIC_API_KEY", "INTERNAL PROMPT", "APPLICATION_PRIVATE"):
            self.assertNotIn(prohibited, serialized)
        self.assertFalse(report["summary"]["semantic_entailment_verified"])

    def test_limit_and_invalid_private_metrics_fail_closed(self) -> None:
        for invalid in (0, True, 1001, "100"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluation_report(self.store, limit=invalid)
        for i in range(4):
            self.write(agent=f"agent-{i}", provider="local", payload={"latency_ms": -5, "usage": {"prompt_tokens": True}})
        report = evaluation_report(self.store, limit=2)
        self.assertTrue(report["sample_truncated"])
        self.assertIsNone(report["summary"]["latency_p50_ms"])
        self.assertEqual(report["summary"]["usage_reported"], 0)

    def test_private_http_evaluation_contract(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/evaluations", timeout=5) as response:
                self.assertEqual(response.status, 200)
                result = json.load(response)
            self.assertEqual(result["scope"], "single_owner_local_run_ledger")
            self.assertEqual(result["schema_version"], 1)
            self.assertNotIn("secrets", json.dumps(result))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
