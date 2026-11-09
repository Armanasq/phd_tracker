from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.workspace_controls import control_context


class ForkControlsTests(unittest.TestCase):
    def test_fork_state_and_ids_are_not_inherited_from_upstream(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "user_opportunities.json").write_text(json.dumps({
                "schema_version": 1, "records": [
                    {"id": "MY_APP", "name": "My own programme"},
                    {"id": "MY_CAND", "name": "My candidate", "record_type": "candidate"},
                ],
            }), encoding="utf-8")
            file, ids = control_context(root, "AnotherUser/my-atlas", "source")
            self.assertEqual(file, root / "data" / "user_workspace_overrides.json")
            self.assertEqual(ids, {"MY_APP", "MY_CAND"})
            self.assertNotIn("APP1", ids)

    def test_fork_owner_updates_fail_closed_before_source_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("starter", "invalid"):
                with self.assertRaisesRegex(ValueError, "starter mode"):
                    control_context(root, "AnotherUser/my-atlas", mode)
            with self.assertRaisesRegex(ValueError, "user_opportunities.json"):
                control_context(root, "AnotherUser/my-atlas", "source")


if __name__ == "__main__":
    unittest.main()
