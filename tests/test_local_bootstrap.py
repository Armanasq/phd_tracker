from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.server import prepare_public_snapshot


class LocalBootstrapTests(unittest.TestCase):
    def test_clean_local_clone_initializes_safe_starter_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "site").mkdir()
            (root / "site" / "index.html").write_text("<html></html>", encoding="utf-8")
            with patch.dict(os.environ, {"PHD_ATLAS_REPOSITORY": "ForkOwner/local-tracker", "PHD_ATLAS_DATA_MODE": ""}):
                result = prepare_public_snapshot(root)
            output = root / "site" / "data" / "workspace.json"
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["instance"]["data_mode"], "starter")
            self.assertEqual(saved["records"], [])
            self.assertEqual(result["repository"], "ForkOwner/local-tracker")

    def test_explicit_local_source_opt_in_loads_only_current_repo_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "site").mkdir()
            (root / "site" / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / "experience_view.json").write_text(json.dumps({
                "as_of": "2026-11-09",
                "applications": [{"id": "LOCAL-01", "name": "My own researched PhD", "deadline": None}],
            }), encoding="utf-8")
            with patch.dict(os.environ, {"PHD_ATLAS_REPOSITORY": "ForkOwner/local-tracker", "PHD_ATLAS_DATA_MODE": "source"}):
                result = prepare_public_snapshot(root)
            saved = json.loads((root / "site" / "data" / "workspace.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in saved["records"]], ["LOCAL-01"])
            self.assertEqual(result["data_mode"], "source")

    def test_incomplete_clone_fails_before_serving(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "site directory is missing"):
                prepare_public_snapshot(Path(directory))


if __name__ == "__main__":
    unittest.main()
