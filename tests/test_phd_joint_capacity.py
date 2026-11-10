from __future__ import annotations

import math
import unittest
from datetime import date

from phd_agents.capacity import joint_capacity_schedule

TODAY = date(2026, 11, 9)


def app(identity, deadline, hours, documents=None, states=None, **kwargs):
    return {
        "id": identity, "record_type": "tracked", "status": "preparing",
        "deadline": deadline, "estimated_hours": hours, "documents": documents or [],
        "document_states": states or {}, **kwargs,
    }


class JointCapacityTests(unittest.TestCase):
    def test_joint_shortfall_despite_individually_feasible_applications(self):
        plan = joint_capacity_schedule([app("A", "2026-11-10", 1.5), app("B", "2026-11-10", 1.5)], TODAY, 7)
        self.assertEqual(plan["baseline"]["total_hours_unallocated"], 1)
        self.assertEqual(plan["deadline_bottlenecks"][0]["minimum_shortfall_hours"], 1)
        self.assertEqual(plan["status"], "over_capacity")

    def test_one_shared_document_changes_additive_workload(self):
        rows = [
            app("A", "2026-11-12", 1, ["academic_cv"], {"academic_cv": "not_started"}),
            app("B", "2026-11-12", 1, ["academic_cv"], {"academic_cv": "in_progress"}),
        ]
        plan = joint_capacity_schedule(rows, TODAY, 7, {"document_effort": {"academic_cv": 3}})
        self.assertEqual(plan["baseline"]["total_work_hours"], 2)
        self.assertEqual(plan["with_shared_documents"]["total_work_hours"], 5)
        self.assertEqual(plan["with_shared_documents"]["total_hours_unallocated"], 1)
        self.assertEqual(len([x for x in plan["scheduled"] if x["task_type"] == "document"]), 3)

    def test_unknown_effort_is_not_assumed_zero(self):
        plan = joint_capacity_schedule([
            app("unknown", "2026-11-15", None, ["academic_cv"], {"academic_cv": "unknown"}),
            app("known", "2026-11-11", 1),
        ], TODAY, 14)
        self.assertEqual(plan["status"], "unresolved_inputs")
        self.assertEqual(plan["unknown_effort_or_date"][0]["application_id"], "unknown")
        self.assertEqual(plan["unknown_document_effort"][0]["document"], "academic_cv")
        self.assertEqual(plan["with_shared_documents"]["total_work_hours"], 1)

    def test_ready_document_consumes_no_shared_hours(self):
        plan = joint_capacity_schedule([
            app("A", "2026-11-11", 1, ["academic_cv"], {"academic_cv": "ready"}),
        ], TODAY, 7, {"document_effort": {"academic_cv": 3}})
        self.assertEqual(plan["shared_document_hours"], {})
        self.assertEqual(plan["with_shared_documents"]["total_work_hours"], 1)

    def test_earliest_deadline_document_priority_and_daily_budget(self):
        rows = [
            app("A", "2026-11-12", 3, ["academic_cv"], {"academic_cv": "in_progress"}),
            app("B", "2026-11-10", 1, ["academic_cv"], {"academic_cv": "not_started"}),
        ]
        plan = joint_capacity_schedule(rows, TODAY, 14, {"document_effort": {"academic_cv": 5}})
        self.assertGreaterEqual(plan["with_shared_documents"]["total_hours_unallocated"], 2)
        by_day = {}
        for block in plan["scheduled"]:
            by_day[block["date"]] = by_day.get(block["date"], 0) + block["hours"]
        self.assertTrue(all(value <= 2.001 for value in by_day.values()))
        self.assertTrue(any(row["task_id"] == "document:academic_cv" for row in plan["unallocated"]))

    def test_namespaced_task_ids_do_not_collide(self):
        plan = joint_capacity_schedule([
            app("document:academic_cv", "2026-11-11", 1, ["academic_cv"], {"academic_cv": "in_progress"}),
        ], TODAY, 14, {"document_effort": {"academic_cv": 1}})
        self.assertEqual(plan["with_shared_documents"]["total_work_hours"], 2)
        self.assertEqual(len({block["task_id"] for block in plan["scheduled"]}), 2)

    def test_unknown_requirements_are_not_declared_feasible(self):
        plan = joint_capacity_schedule([app("A", "2026-11-10", 1)], TODAY, 14)
        self.assertEqual(plan["unconfirmed_document_requirements"], ["A"])
        self.assertEqual(plan["status"], "unresolved_inputs")

    def test_invalid_values_and_duplicate_ids_fail_closed(self):
        for bad in (0, -1, 169, True, math.inf, math.nan, "7"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                joint_capacity_schedule([], TODAY, bad)
        with self.assertRaises(ValueError):
            joint_capacity_schedule([app("A", "2026-11-10", 1)] * 2, TODAY, 7)
        for bad in (-1, math.inf, math.nan, True):
            with self.subTest(effort=bad), self.assertRaises(ValueError):
                joint_capacity_schedule([], TODAY, 7, {"document_effort": {"academic_cv": bad}})
        with self.assertRaises(ValueError):
            joint_capacity_schedule([app("A", "2026-11-10", 1)] * 501, TODAY, 7)

    def test_dates_after_bounded_horizon_do_not_claim_feasibility(self):
        plan = joint_capacity_schedule([app("far", "2028-12-31", 10)], TODAY, 7)
        self.assertEqual(plan["status"], "unresolved_inputs")
        self.assertIn("365-day", plan["unknown_effort_or_date"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
