from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from scripts.build_workspace import build
from scripts.instance_config import (
    action_center_url, pages_url, prepare_site, repository_url,
    resolve_repository, resolve_data_mode, validate_repository,
)


class InstanceTests(unittest.TestCase):
    def test_repository_validation_and_fork_urls(self):
        self.assertEqual(pages_url("Armanasq/phd_tracker"), "https://armanasq.github.io/phd_tracker/")
        self.assertEqual(pages_url("ExampleUser/research"), "https://exampleuser.github.io/research/")
        self.assertEqual(pages_url("ExampleUser/exampleuser.github.io"), "https://exampleuser.github.io/")
        self.assertEqual(pages_url("Team/atlas", "https://atlas.example.org/workspace"), "https://atlas.example.org/workspace/")
        self.assertEqual(repository_url("ExampleUser/research"), "https://github.com/ExampleUser/research")
        for invalid in ("", "../repo", "user/repo/other", "owner/<script>", "owner/../repo"):
            with self.assertRaises(ValueError):
                validate_repository(invalid)
        for invalid in ("http://example.org", "https://example.org/?token=x", "https://x:y@example.org/", "https://example.org/#x"):
            with self.assertRaises(ValueError):
                pages_url("Team/research", invalid)

    def test_identity_is_explicit_and_scoped(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "ForkOwner/my-tracker", "PHD_ATLAS_REPOSITORY": ""}):
            self.assertEqual(resolve_repository(), "ForkOwner/my-tracker")
            self.assertEqual(resolve_repository("Chosen/atlas"), "Chosen/atlas")
        with patch.dict(os.environ, {"PHD_ATLAS_ACTION_ISSUE": ""}):
            self.assertEqual(action_center_url("Armanasq/phd_tracker"), "https://github.com/Armanasq/phd_tracker/issues/1")
            self.assertIn("template=00-owner-action-center.md", action_center_url("ForkOwner/my-tracker"))
            self.assertEqual(action_center_url("ForkOwner/my-tracker", 42), "https://github.com/ForkOwner/my-tracker/issues/42")
            with self.assertRaises(ValueError):
                action_center_url("ForkOwner/my-tracker", "../42")

    def test_new_forks_start_without_inherited_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "experience_view.json").write_text(json.dumps({
                "applications": [{"id": "private-data", "name": "Not reviewed for publication"}],
            }), encoding="utf-8")
            with patch.dict(os.environ, {"PHD_ATLAS_DATA_MODE": ""}):
                snapshot = build(root, repository="NewOwner/new-atlas")
            self.assertEqual(snapshot["records"], [])
            self.assertEqual(snapshot["meta"]["tracked"], 0)
            self.assertEqual(snapshot["instance"]["data_mode"], "starter")
            self.assertNotIn("private-data", json.dumps(snapshot))
            self.assertEqual(snapshot["source_links"]["repository"], "https://github.com/NewOwner/new-atlas")
            self.assertEqual(resolve_data_mode("Armanasq/phd_tracker", ""), "source")
            self.assertEqual(resolve_data_mode("NewOwner/new-atlas", ""), "starter")
            self.assertEqual(resolve_data_mode("NewOwner/new-atlas", "source"), "source")
            with self.assertRaises(ValueError):
                resolve_data_mode("NewOwner/new-atlas", "inherit")

    def test_metadata_is_prepared_for_fork_without_touching_source(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "index.html").write_text(
                '<link rel="canonical" href="https://armanasq.github.io/phd_tracker/">'
                '<meta property="og:url" content="https://armanasq.github.io/phd_tracker/">'
                '<a class="side-link" href="https://github.com/Armanasq/phd_tracker">'
                '<a href="https://github.com/Armanasq/phd_tracker/releases" target="_blank" rel="noopener noreferrer">Release history</a>'
                '<link href="./responsive.css" rel="stylesheet">',
                encoding="utf-8",
            )
            (site / "sitemap.xml").write_text("upstream", encoding="utf-8")
            result = prepare_site(site, "ForkOwner/my-tracker", commit="a" * 40)
            html = (site / "index.html").read_text(encoding="utf-8")
            self.assertEqual(result["repository"], "ForkOwner/my-tracker")
            self.assertIn('href="https://forkowner.github.io/my-tracker/"', html)
            self.assertIn('href="https://github.com/ForkOwner/my-tracker"', html)
            self.assertIn('responsive.css?rev=' + "a" * 40, html)
            urls = [el.text for el in ElementTree.parse(site / "sitemap.xml").iter() if el.tag.endswith("loc")]
            self.assertEqual(urls, ["https://forkowner.github.io/my-tracker/", "https://forkowner.github.io/my-tracker/evidencegraph/"])
            self.assertEqual(json.loads((site / "instance.json").read_text())["private_backend_included"], False)

    def test_fork_build_uses_own_links_and_only_supplied_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "experience_view.json").write_text(json.dumps({
                "as_of": "2026-11-09",
                "applications": [{"id": "own-1", "name": "Documented opportunity", "deadline": "2027-01-31"}],
            }), encoding="utf-8")
            with patch.dict(os.environ, {"PHD_ATLAS_ACTION_ISSUE": ""}):
                snapshot = build(root, repository="ForkOwner/my-tracker", data_mode="source")
            self.assertEqual([r["id"] for r in snapshot["records"]], ["own-1"])
            self.assertEqual(snapshot["source_links"]["repository"], "https://github.com/ForkOwner/my-tracker")
            self.assertIn("template=00-owner-action-center.md", snapshot["source_links"]["control_issue"])
            self.assertEqual(snapshot["instance"]["type"], "independent")
            self.assertEqual(snapshot["meta"]["tracked"], 1)
            self.assertEqual([item["path"] for item in snapshot["coverage"]["files"]], ["data/experience_view.json"])


if __name__ == "__main__":
    unittest.main()
