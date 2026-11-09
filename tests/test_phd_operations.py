from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from phd_agents.catalog import agent_spec, workflow_spec
from phd_agents.operations import evidence_conflicts, milestones_for, normalize_item, referee_matrix, research_fit_signals, resource_schedule
from phd_agents.store import Store
from phd_agents.toolkit import run_tools


def opportunity(**patch):
    item = {"id": "APP1", "name": "SLAM and robot learning PhD", "record_type": "tracked",
            "deadline": "2026-11-10", "deadline_type": "final", "verification": "source_verified",
            "status": "preparing", "documents": ["academic_cv"],
            "document_states": {"academic_cv": "unknown"}, "estimated_hours": 8,
            "priority": "high", "next_step": "Confirm primary portal", "source_url": "https://example.edu/jobs"}
    item.update(patch)
    return item


class OperationsTests(unittest.TestCase):
    def test_private_object_roundtrip_and_referee_matrix(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d) / "state.sqlite")
            self.addCleanup(store.close)
            store.put_item("referee", {"id": "person1", "name": "Professor X", "contact": "private@example.com"})
            store.put_item("reference", {"id": "letter1", "referee_id": "person1",
                                          "application_id": "APP1", "status": "requested", "deadline": "2026-11-11"})
            store.put_item("reference", {"id": "letter2", "referee_id": "person1",
                                          "application_id": "APP2", "status": "uploaded", "deadline": "2026-11-12"})
            matrix = referee_matrix(store.items("referee"), store.items("reference"), date(2026,11,9))
            self.assertEqual(matrix["pending"], 2)
            self.assertEqual(matrix["urgent"], 2)
            self.assertEqual(matrix["shared_dependency"], {"person1": 2})
            self.assertTrue(store.delete_item("reference", "letter1"))
            self.assertEqual(len(store.items("reference")), 1)
            self.assertTrue(all("private@example.com" not in str(x) for x in store.activity()))

    def test_milestones_preserve_time_classification(self):
        record = opportunity()
        milestone = normalize_item("milestone", {"id": "special1", "application_id": "APP1",
             "kind": "scholarship", "date": "2026-11-14", "time": "17:00",
             "timezone": "Europe/London", "verification": "primary_confirmed",
             "source_url": "https://example.edu/funding"})
        timeline = milestones_for([record], [milestone], date(2026, 11, 9))
        self.assertEqual(len(timeline), 2)
        self.assertTrue(next(x for x in timeline if x["id"] == "special1")["cutoff_fully_verified"])
        self.assertFalse(next(x for x in timeline if x["id"] == "source:APP1")["cutoff_fully_verified"])
        with self.assertRaises(ValueError):
            normalize_item("milestone", {"id": "special1", "application_id": "APP1",
                "kind": "final", "date": "2026-11-14", "time": "17:00"})

    def test_evidence_conflicts_not_silently_resolved(self):
        claims = [
            {"id": "a", "application_id": "APP1", "field": "deadline", "assertion": "15 November", "status": "primary_confirmed"},
            {"id": "b", "application_id": "APP1", "field": "deadline", "assertion": "9 November", "status": "unverified"},
        ]
        self.assertEqual(evidence_conflicts(claims)[0]["status"], "needs_manual_resolution")
        claims[1]["status"] = "superseded"
        self.assertEqual(evidence_conflicts(claims), [])

    def test_research_fit_and_resource_schedule_are_explicit_heuristics(self):
        profile = {"research_topics": ["SLAM"], "skills": ["robot learning"],
                   "hours_per_week": 7, "document_effort": {"academic_cv": 4}}
        match = research_fit_signals(profile, [opportunity()])
        self.assertEqual(match[0]["matched_count"], 2)
        schedule = resource_schedule([opportunity()], date(2026, 11, 9), 7, profile)
        self.assertEqual(len(schedule["unallocated"]), 1)
        self.assertGreater(schedule["unallocated"][0]["hours_unallocated"], 0)
        self.assertIn("academic_cv", schedule["shared_document_hours"])

    def test_agent_tools_run_without_unsafe_side_effects(self):
        profile = {"id": "applicant", "skills": ["SLAM"], "hours_per_week": 12}
        tool_pack = run_tools(["preflight","research_alignment","referee_dependencies"],
            data={"providers": []}, records=[opportunity()], today=date(2026, 11, 9),
            private={"profile": [profile], "referee": [], "reference": [], "milestone": [], "evidence": []},
            application_id="APP1")
        self.assertEqual(tool_pack["count"], 3)
        self.assertEqual(tool_pack["side_effects"], "none")
        self.assertEqual(tool_pack["tools"][0]["name"], "preflight")
        with self.assertRaises(ValueError):
            run_tools(["arbitrary_shell"], data={}, records=[], private={}, today=date(2026, 11, 9))

    def test_agent_and_workflow_tool_config_validation(self):
        a=agent_spec({"id": "custom1", "label": "My agent", "instructions": "Review evidence", "tools": ["preflight", "deadline_clocks"]})
        self.assertEqual(a["tools"], ["preflight", "deadline_clocks"])
        with self.assertRaises(ValueError):
            agent_spec({"id": "custom1", "label": "My agent", "instructions": "Review evidence", "tools": ["shell"]})
        w=workflow_spec({"id": "custom_flow", "agent_id": "custom1", "steps": ["custom1", "portfolio_planner"],
                         "schedule": "weekly", "provider_id": "ollama"})
        self.assertEqual(len(w["steps"]), 2)
        with self.assertRaises(ValueError):
            workflow_spec({"id": "custom_flow", "agent_id": "custom1", "steps": ["a", "b", "c", "d"]})


if __name__ == "__main__":
    unittest.main()
