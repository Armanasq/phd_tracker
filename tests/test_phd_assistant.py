from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.engine import run_agent
from phd_agents.providers import ModelReply
from phd_agents.relevance import reference, select_evidence
from phd_agents.server import ApiServer
from phd_agents.store import Store


def example_records() -> list[dict]:
    return [
        {
            "id": "AI-001", "name": "Robotics and visual SLAM PhD",
            "record_type": "tracked", "topic": "Robotics, mapping, navigation",
            "country": "Germany", "deadline": "2027-01-11", "status": "preparing",
            "verification": "source_verified", "source_url": "https://university.example.edu/robotics",
            "next_step": "Contact faculty", "documents": ["research_statement"],
        },
        {
            "id": "BIO-002", "name": "Computational genomics PhD",
            "record_type": "tracked", "topic": "Genomics and sequence modeling",
            "country": "Netherlands", "deadline": "2027-01-02",
            "status": "preparing", "verification": "unverified",
            "source_url": "http://unverified.example.edu/apply",
        },
        {
            "id": "OLD-003", "name": "Archived robotics PhD",
            "record_type": "tracked", "topic": "Navigation",
            "country": "Canada", "deadline": "2025-01-01",
            "status": "archived", "verification": "unverified",
        },
    ]


class RelevanceTests(unittest.TestCase):
    def test_field_weighted_ranking_and_verifiable_references(self):
        match = select_evidence("visual SLAM robotics", example_records(), today=date(2026, 11, 9))
        self.assertEqual(match["method"], "weighted_lexical")
        self.assertEqual(match["records"][0]["id"], "AI-001")
        self.assertEqual(match["references"][0]["application_id"], "AI-001")
        self.assertIn("name", match["references"][0]["matched_fields"])
        self.assertNotIn("notes", match["records"][0])

    def test_selected_application_overrides_rank_and_limits_scope(self):
        result = select_evidence("robotics", example_records(), application_id="BIO-002")
        self.assertEqual(result["method"], "selected_application")
        self.assertEqual(len(result["references"]), 1)
        self.assertIsNone(result["references"][0]["source_url"])
        with self.assertRaisesRegex(ValueError, "Unknown application"):
            select_evidence("robotics", example_records(), application_id="missing")

    def test_no_match_falls_back_to_upcoming_not_expired(self):
        result = select_evidence("unrelated gibberish", example_records(), today=date(2026, 11, 9))
        self.assertEqual(result["method"], "deadline_fallback")
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual([r["id"] for r in result["records"]], ["BIO-002", "AI-001"])

    def test_query_and_source_are_bounded(self):
        self.assertIsNone(reference({"id": "A", "source_url": "http://example.org"}, [])["source_url"])
        with self.assertRaises(ValueError):
            select_evidence(42, [])
        with self.assertRaises(ValueError):
            select_evidence("a", [], limit=30)


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private.sqlite")
        self.addCleanup(self.store.close)

    def test_private_thread_scope_history_and_delete(self):
        run_id = self.store.put_run("agent", "research_fit", "AI-001", "proposed", "ollama", {
            "text": "Source needed", "evidence_refs": [{"application_id": "AI-001", "name": "Robotics"}],
            "retrieval_method": "selected_application", "latency_ms": 15, "tools": ["preflight"],
        })
        identity = self.store.save_conversation_turn(
            conversation_id=None, agent_id="research_fit", application_id="AI-001",
            question="What about SLAM?", answer="Source needed", model="local",
            provider_id="ollama", run_id=run_id,
        )
        self.assertEqual(len(identity), 32)
        saved = self.store.conversation(identity)
        self.assertEqual([x["role"] for x in saved["messages"]], ["user", "assistant"])
        self.assertEqual(saved["messages"][1]["evidence_refs"][0]["application_id"], "AI-001")
        self.assertEqual(saved["messages"][1]["run_id"], run_id)
        self.assertEqual(len(self.store.conversation_context(identity, "research_fit", "AI-001")), 2)
        with self.assertRaisesRegex(ValueError, "scoped"):
            self.store.conversation_context(identity, "research_fit", "BIO-002")
        with self.assertRaisesRegex(ValueError, "scoped"):
            self.store.conversation_context(identity, "deadline_auditor", "AI-001")
        self.assertEqual(self.store.conversations()[0]["id"], identity)
        self.assertTrue(self.store.delete_conversation(identity))
        with self.assertRaisesRegex(ValueError, "Unknown conversation"):
            self.store.conversation(identity)

    def test_input_and_scope_validation(self):
        with self.assertRaises(ValueError):
            self.store.save_conversation_turn(
                conversation_id=None, agent_id="research_fit", application_id=None,
                question="", answer="Response", model="local", provider_id="ollama", run_id="run",
            )
        with self.assertRaises(ValueError):
            self.store.conversation("../../../etc/passwd")


class AssistantExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private.sqlite")
        self.addCleanup(self.store.close)
        self.data = {"as_of": "2026-11-09", "providers": [], "meta": {"tracked": 3}}

    def test_relevance_and_history_in_prompt(self):
        received = []
        def model(provider, system, prompt):
            received.append(prompt)
            return ModelReply("Documented evidence only", provider["model"], {"prompt_tokens": 25}, provider["id"], 10)
        with patch("phd_agents.engine.owner_records", return_value=(self.data, example_records())):
            with patch("phd_agents.engine.invoke", side_effect=model):
                first = run_agent(self.store, Path(self.tmp.name), agent_id="research_fit",
                                  conversation_mode=True, input_text="What about SLAM?")
                second = run_agent(self.store, Path(self.tmp.name), agent_id="research_fit",
                                   conversation_mode=True, conversation_id=first["conversation_id"],
                                   input_text="And the next steps?")
        self.assertEqual(first["evidence_refs"][0]["application_id"], "AI-001")
        self.assertEqual(first["retrieval_method"], "weighted_lexical")
        self.assertEqual(second["conversation_id"], first["conversation_id"])
        self.assertIn("<conversation_history>", received[1])
        self.assertIn("What about SLAM?", received[1])
        self.assertNotIn("<conversation_history>", received[0])
        self.assertEqual(len(self.store.conversation(first["conversation_id"])["messages"]), 4)
        self.assertEqual(len(self.store.runs()), 2)
        with patch("phd_agents.engine.owner_records", return_value=(self.data, example_records())):
            with self.assertRaisesRegex(ValueError, "scoped"):
                run_agent(self.store, Path(self.tmp.name), agent_id="research_fit",
                          application_id="BIO-002", conversation_mode=True,
                          conversation_id=first["conversation_id"], input_text="Now genomics")

    def test_conversation_requires_message(self):
        with self.assertRaisesRegex(ValueError, "message"):
            run_agent(self.store, Path(self.tmp.name), agent_id="research_fit",
                      input_text=" ", conversation_mode=True)


class AssistantServerTests(unittest.TestCase):
    def test_private_bootstrap_and_conversation_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data.sqlite")
            server = ApiServer(("127.0.0.1", 0), store=store, root=Path(tmp))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/assistant/bootstrap", timeout=4) as response:
                    bootstrap = json.load(response)
                self.assertTrue(bootstrap["security"]["local_only"])
                self.assertIn("agent_assignments", bootstrap["routing"])
                self.assertEqual(bootstrap["conversations"], [])
                with urlopen(base + "/api/conversations", timeout=4) as response:
                    self.assertEqual(json.load(response), {"conversations": []})
                request = Request(base + "/api/conversations/not-a-uuid")
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=4)
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
                store.close()

    def test_health_remains_responsive_during_model_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data.sqlite")
            server = ApiServer(("127.0.0.1", 0), store=store, root=Path(tmp))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            started = threading.Event()
            release = threading.Event()
            completed: list[object] = []

            def slow_inference(provider, system, prompt):
                started.set()
                if not release.wait(timeout=5):
                    raise RuntimeError("Test model timed out")
                return ModelReply("Complete", provider["model"], {}, provider["id"])

            def send():
                try:
                    request = Request(base + "/api/agents/run",
                                      data=json.dumps({"agent_id": "research_fit", "input_text": "Robotics"}).encode(),
                                      headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(request, timeout=8) as response:
                        completed.append(json.load(response))
                except Exception as error:
                    completed.append(error)

            try:
                with patch("phd_agents.engine.owner_records", return_value=(
                    {"as_of": "2026-11-09", "providers": [], "meta": {}}, example_records(),
                )):
                    with patch("phd_agents.engine.invoke", side_effect=slow_inference):
                        worker = threading.Thread(target=send, daemon=True)
                        worker.start()
                        self.assertTrue(started.wait(timeout=4))
                        with urlopen(base + "/api/health", timeout=2) as response:
                            self.assertEqual(json.load(response)["status"], "ok")
                        release.set()
                        worker.join(timeout=6)
                        self.assertFalse(worker.is_alive())
                        self.assertEqual(completed[0]["text"], "Complete")
            finally:
                release.set()
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
                store.close()


if __name__ == "__main__":
    unittest.main()
