from __future__ import annotations

import unittest

from scripts.notification_engine import distinct_daily_actions


class ActionCenterDigestTests(unittest.TestCase):
    def test_repeated_workbook_tasks_are_rendered_once(self) -> None:
        repeated = {"action": "  Confirm   supervisors  ", "name": "Research PhD", "due": "2026-11-10"}
        alternate = {"action": "Confirm supervisors", "name": "Research PhD", "due": "2026-11-11"}
        daily = {
            "eligible_application_deadlines": [repeated],
            "cross_route_tasks": [{"action": "Confirm supervisors", "name": "Research PhD", "due": "2026-11-10"}],
            "scheduled_timeline_tasks": [alternate],
        }
        result = distinct_daily_actions(daily)
        self.assertEqual(len(result), 2)
        self.assertIn("Confirm supervisors", result[1])

    def test_distinct_actions_are_selected_before_limit(self) -> None:
        daily = {"cross_route_tasks": [
            {"action": "Prepare CV", "name": "A", "due": "2026-11-10"},
            {"action": "Prepare CV", "name": "A", "due": "2026-11-10"},
            {"action": "Prepare proposal", "name": "B", "due": "2026-11-10"},
        ]}
        self.assertEqual(len(distinct_daily_actions(daily, limit=2)), 2)

    def test_input_validation_and_missing_action(self) -> None:
        self.assertEqual(distinct_daily_actions({"scheduled_timeline_tasks": [{}]}), [])
        with self.assertRaises(ValueError):
            distinct_daily_actions([], limit=13)
        with self.assertRaises(ValueError):
            distinct_daily_actions({}, limit=0)


if __name__ == "__main__":
    unittest.main()
