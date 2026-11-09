from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.engine import paper_radar_for_instance
from phd_agents.secrets import secret_path
from phd_agents.store import default_path, private_directory


class IndependentRuntimeIsolationTests(unittest.TestCase):
    def test_fork_storage_is_checkouts_and_repositories_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root_a = home / "clone-a"
            root_b = home / "clone-b"
            upstream = private_directory(root_a, "Armanasq/phd_tracker", home=home)
            self.assertEqual(upstream, home / ".local" / "share" / "phd-atlas")
            one = private_directory(root_a, "ForkOwner/phd_tracker", home=home)
            two = private_directory(root_b, "ForkOwner/phd_tracker", home=home)
            other = private_directory(root_a, "AnotherOwner/phd_tracker", home=home)
            self.assertEqual(one, private_directory(root_a, "ForkOwner/phd_tracker", home=home))
            self.assertEqual(len({str(one), str(two), str(other), str(upstream)}), 4)
            self.assertFalse(any("ForkOwner" in str(item) for item in (one, two)))
            self.assertNotEqual(one, upstream)

    def test_explicit_private_directory_controls_database_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"PHDAI_PRIVATE_DIR": directory}):
                self.assertEqual(default_path(), Path(directory) / "state.sqlite3")
                self.assertEqual(secret_path(), Path(directory) / "provider-credentials.json")

    def test_paper_radar_never_reads_upstream_records_in_fork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            upstream_papers = {"papers": [{"title": "Upstream maintained research", "published": "2026-01-01"}]}
            (root / "data" / "research_radar.json").write_text(json.dumps(upstream_papers), encoding="utf-8")
            fork = {"instance": {"type": "independent"}}
            upstream = {"instance": {"type": "upstream"}}
            self.assertEqual(paper_radar_for_instance(root, fork), [])
            self.assertEqual(paper_radar_for_instance(root, upstream)[0]["title"], "Upstream maintained research")
            independent = {"papers": [{"title": "My published paper", "published": "2026-05-20"}]}
            (root / "data" / "user_research_radar.json").write_text(json.dumps(independent), encoding="utf-8")
            self.assertEqual(paper_radar_for_instance(root, fork)[0]["title"], "My published paper")
            (root / "data" / "user_research_radar.json").write_text('{"papers":["not-a-record",{}]}', encoding="utf-8")
            self.assertEqual(len(paper_radar_for_instance(root, fork)), 1)


if __name__ == "__main__":
    unittest.main()
