from __future__ import annotations

import unittest

from scripts.deadline_cutoffs import normalize_cutoff, verified_cutoff_utc


class CutoffTests(unittest.TestCase):
    def test_dst_conversion(self):
        self.assertEqual(verified_cutoff_utc("2027-06-01", "23:59", "Europe/London"), "2027-06-01T22:59:00Z")
        self.assertEqual(verified_cutoff_utc("2027-01-02", "23:59", "Europe/London"), "2027-01-02T23:59:00Z")
        self.assertEqual(verified_cutoff_utc("2027-06-01", "23:59", "Europe/Berlin"), "2027-06-01T21:59:00Z")

    def test_dst_invalid(self):
        for day, clock in (("2027-03-28", "01:30"), ("2027-10-31", "01:30")):
            with self.assertRaisesRegex(ValueError, "ambiguous or nonexistent"):
                verified_cutoff_utc(day, clock, "Europe/London")

    def test_verified(self):
        data = {"deadline_time": "23:59", "deadline_timezone": "Europe/London",
                "deadline_cutoff_verified": True,
                "deadline_cutoff_evidence": "Official page says the portal closes at 23:59 in London"}
        value = normalize_cutoff(
            data, deadline="2027-06-01", verification="source_verified",
            source_url="https://example.edu", source_date="2026-11-10",
            deadline_type="final", evidence="Official call reviewed",
        )
        self.assertEqual(value["deadline_cutoff_utc"], "2027-06-01T22:59:00Z")
        self.assertTrue(value["deadline_cutoff_verified"])

    def test_unverified_time_never_yields_instant(self):
        value = normalize_cutoff(
            {"deadline_time": "23:59", "deadline_timezone": "Europe/London"},
            deadline="2027-06-01", verification="unverified", source_url="",
            source_date=None, deadline_type="unverified", evidence="",
        )
        self.assertIsNone(value["deadline_cutoff_utc"])
        self.assertFalse(value["deadline_cutoff_verified"])

    def test_claims_fail_closed(self):
        base = {"deadline_time": "23:59", "deadline_timezone": "Europe/London",
                "deadline_cutoff_verified": True,
                "deadline_cutoff_evidence": "Official cutoff checked 23:59"}
        for changes in ({"deadline_cutoff_verified": "yes"}, {"deadline_cutoff_evidence": ""},
                        {"deadline_time": "24:05"}, {"deadline_timezone": "Invalid/Region"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_cutoff(
                    {**base, **changes}, deadline="2027-06-01", verification="source_verified",
                    source_url="https://example.edu", source_date="2026-11-10",
                    deadline_type="final", evidence="Official call reviewed",
                )
        with self.assertRaises(ValueError):
            normalize_cutoff(
                base, deadline="2027-06-01", verification="unverified",
                source_url="https://example.edu", source_date="2026-11-10",
                deadline_type="final", evidence="Official call reviewed",
            )


if __name__ == "__main__":
    unittest.main()
