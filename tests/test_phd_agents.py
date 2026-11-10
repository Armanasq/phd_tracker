from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.catalog import AGENTS, PROVIDERS, WORKFLOWS, agent_spec, provider_spec, workflow_spec
from phd_agents.domain import agenda, plan_capacity, preflight
from phd_agents.engine import run_agent, scheduler_once
from phd_agents.providers import ModelReply, validate_url
from phd_agents.server import ApiServer
from phd_agents.store import ConflictError, Store


def make_record(**changes):
    result = {
        "id": "APP1", "record_type": "tracked", "name": "Verified robotics research PhD",
        "status": "preparing", "verification": "source_verified",
        "deadline": "2026-11-20", "deadline_type": "final",
        "documents": ["academic_cv"], "document_states": {"academic_cv": "unknown"},
        "source_url": "https://university.example.edu/apply", "apply_url": "",
        "funding": "Funding claimed; personal eligibility unknown",
        "eligibility": "Not independently established", "next_step": "Confirm supervisor availability",
        "priority": "normal", "duplicate_submission_advisory": False,
    }
    result.update(changes)
    return result


class CatalogTests(unittest.TestCase):
    def test_builtin_catalog_ids_are_unique(self):
        for entries in (AGENTS, PROVIDERS, WORKFLOWS):
            self.assertEqual(len(entries), len({x["id"] for x in entries}))

    def test_provider_validation(self):
        self.assertEqual(validate_url("http://127.0.0.1:11434/v1", True), "http://127.0.0.1:11434/v1")
        with self.assertRaises(ValueError):
            validate_url("http://example.com/v1", True)
        with self.assertRaises(ValueError):
            validate_url("http://192.168.1.2:8888/v1", True)
        with self.assertRaises(ValueError):
            validate_url("https://user:secret@example.com", False)
        with self.assertRaises(ValueError):
            provider_spec({"id": "bad model", "kind": "openai_compatible", "base_url": "https://example.com", "model": "a"})

    def test_provider_inference_parameters_are_explicit_and_validated(self):
        data = {"id": "custom_local", "kind": "openai_compatible",
                "base_url": "http://127.0.0.1:8000/v1", "model": "local",
                "local": True, "max_output_tokens": 8192, "timeout_seconds": 90,
                "temperature": 0.25}
        provider = provider_spec(data)
        self.assertEqual(provider["timeout_seconds"], 90)
        self.assertEqual(provider["max_output_tokens"], 8192)
        self.assertEqual(provider["temperature"], 0.25)
        for bad in ({"timeout_seconds": 0}, {"timeout_seconds": 181}, {"temperature": 3.0},
                    {"temperature": True}, {"max_output_tokens": 17000}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                provider_spec({**data, **bad})
        self.assertNotIn("temperature", provider_spec({k: v for k, v in data.items() if k != "temperature"}))

    def test_workflow_contract_preserves_execution_policy(self):
        flow = workflow_spec({"id": "private_daily", "agent_id": "portfolio_planner", "schedule": "daily",
                              "enabled": True, "provider_id": "openai", "cloud_consent": True,
                              "prompt": "Audit only confirmed source evidence"})
        self.assertTrue(flow["cloud_consent"])
        self.assertEqual(flow["provider_id"], "openai")
        self.assertEqual(flow["prompt"], "Audit only confirmed source evidence")
        with self.assertRaises(ValueError):
            workflow_spec({"id": "bad", "agent_id": "portfolio_planner", "schedule": "every-minute"})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private.db")
        self.addCleanup(self.store.close)

    def test_private_write_and_optimistic_conflict(self):
        with self.assertRaises(ValueError):
            self.store.update_application("APP1", {"status": "submitted"}, 0)
        stored = self.store.update_application("APP1", {"status": "submitted", "confirmed_submission": True}, 0)
        self.assertEqual(stored["version"], 1)
        self.assertEqual(self.store.get_application("APP1")["status"], "submitted")
        with self.assertRaises(ConflictError):
            self.store.update_application("APP1", {"status": "preparing"}, 0)
        self.assertTrue(any(x["action"] == "application:update" for x in self.store.activity()))

    def test_document_state_and_private_note(self):
        value = self.store.update_application("APP1", {
            "notes": "Sensitive statement remains in the SQLite vault",
            "document_states": {"academic_cv": "ready"}, "estimated_hours": 12.5}, 0)
        self.assertEqual(value["document_states"]["academic_cv"], "ready")
        self.assertNotIn("confirmed_submission", value)
        with self.assertRaises(ValueError):
            self.store.update_application("APP1", {"notes": "x" * 4000}, 1)

    def test_catalog_upserts_and_schedule_marker(self):
        self.store.put_custom("agent", agent_spec({"id": "new_agent", "label": "Custom", "instructions": "Audit sources only"}))
        self.assertEqual(len(self.store.get_custom("agent")), 1)
        self.assertIsNone(self.store.schedule_last("brief"))
        self.store.schedule_mark("brief", "2026-11-09")
        self.assertEqual(self.store.schedule_last("brief"), "2026-11-09")


class DomainTests(unittest.TestCase):
    def test_preflight_never_claims_ready_on_unknowns(self):
        result = preflight(make_record(), date(2026, 11, 9))
        self.assertFalse(result["ready"])
        self.assertGreater(result["counts"]["unknown"], 0)
        self.assertTrue(any(x["code"] == "cutoff_time" for x in result["checks"]))

    def test_duplicate_route_blocks_preflight(self):
        result = preflight(make_record(duplicate_submission_advisory=True), date(2026, 11, 9))
        self.assertGreater(result["counts"]["blocker"], 0)
        self.assertFalse(result["ready"])

    def test_submitted_application_keeps_followup_queue(self):
        rows = [make_record(status="submitted", followup="2026-11-10")]
        tasks = agenda(rows, date(2026, 11, 9))
        self.assertTrue(any(x["kind"] == "post_submission" for x in tasks))

    def test_capacity_avoids_fabricated_estimates(self):
        records = [make_record()]
        result = plan_capacity(records, date(2026, 11, 9), 15)
        self.assertIn("APP1", result["unknown_effort"])
        self.assertEqual(result["scheduled"], [])
        result = plan_capacity([make_record(estimated_hours=10)], date(2026, 11, 9), 15)
        self.assertEqual(result["scheduled"][0]["estimated_hours"], 10)
        with self.assertRaises(ValueError):
            plan_capacity(records, date(2026, 11, 9), -1)


class AgentExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "state.db")
        self.addCleanup(self.store.close)
        self.data = {"timezone": "Europe/London", "as_of": "2026-11-09",
                     "providers": [], "meta": {"tracked": 1}}

    def test_cloud_consent_and_audited_proposal(self):
        with patch("phd_agents.engine.owner_records", return_value=(self.data, [make_record()])):
            with self.assertRaises(PermissionError):
                run_agent(self.store, Path(self.tmp.name), agent_id="portfolio_planner", provider_id="openai")
            with patch("phd_agents.engine.invoke", return_value=ModelReply("Verify source before contacting the lab", "test-model", {"prompt_tokens": 15}, "openai")) as call:
                value = run_agent(self.store, Path(self.tmp.name),
                                  agent_id="portfolio_planner", provider_id="openai",
                                  cloud_consent=True, application_id="APP1")
        self.assertEqual(value["status"], "proposed")
        self.assertEqual(len(self.store.runs()), 1)
        self.assertTrue("untrusted" in call.call_args.args[2])

    def test_captured_source_quote_is_unverified_agent_context(self):
        import hashlib
        from phd_agents.source_text import extract_visible_text
        from phd_agents.source_observer import observe_record
        from phd_agents.source_claims import capture_source_claim
        text = "Official page says applications close on 15 December 2026."
        original = text.encode("utf-8")
        record = make_record()
        observation = observe_record(self.store, "APP1", record["source_url"],
                                     fetcher=lambda _: {
                                         "status": "fetched", "http_status": 200,
                                         "content_length": len(original),
                                         "content_sha256": hashlib.sha256(original).hexdigest(),
                                         **extract_visible_text(original, "text/plain"),
                                     })
        claim = capture_source_claim(
            self.store, observation_id=observation["id"], claim_type="deadline",
            quote=text, candidate_value="2026-12-15",
            expected_digest=observation["content_sha256"],
        )
        citation = "SRC-" + str(claim["id"])
        answer = "Candidate date still needs review. [claim:" + citation + "]"
        with patch("phd_agents.engine.owner_records", return_value=(self.data, [record])):
            with patch("phd_agents.engine.invoke",
                       return_value=ModelReply(answer, "stub-model", {}, "ollama")) as invoke:
                result = run_agent(self.store, Path(self.tmp.name), agent_id="portfolio_planner",
                                   provider_id="ollama", application_id="APP1", input_text="Check deadline evidence")
        prompt = invoke.call_args.args[2]
        self.assertIn("source_claims", prompt)
        self.assertIn("exact_captured_source_quote_not_verified_interpretation", prompt)
        self.assertIn("Official page says applications close", prompt)
        self.assertEqual(result["source_claim_refs"], [citation])
        self.assertEqual(result["claim_audit"]["linked_to_unverified_records"], 1)
        self.assertEqual(result["claim_audit"]["linked_to_reviewed_records"], 0)
        self.assertFalse(result["claim_audit"]["semantic_entailment_verified"])
        self.assertEqual(self.store.get_application("APP1")["version"], 0)

    def test_manual_cloud_run_requires_fresh_consent_even_when_route_is_approved(self):
        from phd_agents.routing import ModelRoute
        from phd_agents.engine import run_workflow
        provider = next(p for p in PROVIDERS if p["id"] == "openai")
        route = ModelRoute(provider=provider, source="agent_assignment", approved=True)
        with patch("phd_agents.engine.resolve_route", return_value=route):
            with patch("phd_agents.engine.invoke") as call:
                with self.assertRaisesRegex(PermissionError, "per-run"):
                    run_agent(self.store, Path(self.tmp.name),
                              agent_id="portfolio_planner", provider_id="openai")
                with self.assertRaisesRegex(PermissionError, "per-run"):
                    run_workflow(self.store, Path(self.tmp.name),
                                 workflow_id="daily_brief", provider_id="openai")
                call.assert_not_called()

    def test_scheduler_only_runs_enabled_workflows_once_per_period(self):
        item = workflow_spec({"id": "private_daily", "agent_id": "portfolio_planner",
                              "schedule": "daily", "enabled": True, "provider_id": "ollama"})
        self.store.put_custom("workflow", item)
        now = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
        with patch("phd_agents.engine.run_workflow", return_value={"id": "test-run"}) as call:
            first = scheduler_once(self.store, Path(self.tmp.name), now=now)
            second = scheduler_once(self.store, Path(self.tmp.name), now=now)
        self.assertEqual(first, [{"workflow_id": "private_daily", "status": "proposed", "run_id": "test-run"}])
        self.assertEqual(second, [])
        self.assertEqual(call.call_count, 1)

    def test_scheduler_refuses_unapproved_cloud_execution(self):
        item = workflow_spec({"id": "private_daily", "agent_id": "portfolio_planner",
                              "schedule": "daily", "enabled": True, "provider_id": "openai"})
        self.store.put_custom("workflow", item)
        result = scheduler_once(self.store, Path(self.tmp.name), now=datetime(2026, 11, 9, tzinfo=timezone.utc))
        self.assertEqual(result[0]["reason"], "cloud_consent_missing")


class ServerTests(unittest.TestCase):
    def test_local_health_endpoint_and_cross_origin_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "db.sqlite")
            server = ApiServer(("127.0.0.1", 0), store=store, root=Path(tmp))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            address = "http://127.0.0.1:" + str(server.server_port)
            try:
                with urlopen(address + "/api/health", timeout=4) as resp:
                    self.assertEqual(json.load(resp)["mode"], "loopback_private")
                request = Request(address + "/api/health", headers={"Origin": "https://untrusted.example"})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=4)
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
                store.close()


if __name__ == "__main__":
    unittest.main()
