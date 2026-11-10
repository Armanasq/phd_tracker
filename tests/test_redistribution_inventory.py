from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.redistribution_inventory import audit_redistribution


class RedistributionInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def create(self, path: str, content: str = "fixture") -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_missing_license_is_reported_without_granting_rights(self) -> None:
        self.create("phd_agents/engine.py")
        self.create("data/imports/upload.json")
        self.create("assets/readme/generated.svg")
        report = audit_redistribution(
            self.root, filenames=[
                "phd_agents/engine.py", "data/imports/upload.json",
                "assets/readme/generated.svg",
            ],
        )
        self.assertFalse(report["license"]["file_present"])
        self.assertFalse(report["license"]["legal_grant_verified"])
        self.assertEqual(report["counts"]["tracked_files"], 3)
        self.assertEqual(report["counts"]["research_data_files"], 1)
        self.assertEqual(report["counts"]["bundled_visual_or_font_assets"], 1)
        self.assertEqual(report["status"], "blocked_pending_rightsholder_and_data_provenance_attestation")

    def test_license_file_alone_does_not_prove_redistribution_authority(self) -> None:
        self.create("LICENSE", "test only")
        report = audit_redistribution(self.root, filenames=["LICENSE"])
        self.assertTrue(report["license"]["file_present"])
        self.assertFalse(report["license"]["legal_grant_verified"])

    def test_external_actions_and_requirements_are_inventory_only(self) -> None:
        self.create(
            "requirements-intelligence.txt",
            "# synthetic private comment\nopenpyxl==3.1.5\npytest==8.4.2 # version\n",
        )
        self.create(
            ".github/workflows/qa.yml",
            "steps:\n  - uses: actions/checkout@v4\n  - uses: ./local\n  - uses: vendor/action@deadbeef\n",
        )
        report = audit_redistribution(
            self.root,
            filenames=[".github/workflows/qa.yml", "requirements-intelligence.txt"],
        )
        self.assertEqual(len(report["python_dependencies"]), 2)
        self.assertEqual(
            [row["reference"] for row in report["workflow_actions"]],
            ["actions/checkout@v4", "vendor/action@deadbeef"],
        )
        self.assertNotIn("synthetic private comment", str(report))

    def test_invalid_paths_and_symlinks_are_rejected(self) -> None:
        self.create("data/test.json")
        for name in ("../secrets", "/tmp/secret", "dir\\filename"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit_redistribution(self.root, filenames=[name])
        (self.root / "link.json").symlink_to(self.root / "data/test.json")
        with self.assertRaises(ValueError):
            audit_redistribution(self.root, filenames=["link.json"])
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "token").write_text("private", encoding="utf-8")
            (self.root / "bridge").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaises(ValueError):
                audit_redistribution(self.root, filenames=["bridge/token"])


if __name__ == "__main__":
    unittest.main()
