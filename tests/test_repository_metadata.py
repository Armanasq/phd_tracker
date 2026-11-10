from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_repository_metadata import api_root, load_metadata, verify_metadata, write_metadata


class GitHubAboutConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "repository-metadata.json"
        self.file.write_text(json.dumps({
            "repository": "Armanasq/phd_tracker",
            "description": "Evidence-backed PhD application workspace",
            "homepage": "https://armanasq.github.io/phd_tracker/",
            "topics": ["phd-tracker", "github-pages"],
        }), encoding="utf-8")

    def test_upstream_metadata_is_unchanged(self) -> None:
        with patch.dict(os.environ, {"PHD_ATLAS_SITE_URL": ""}):
            data = load_metadata(self.file, repository="Armanasq/phd_tracker")
        self.assertEqual(data["homepage"], "https://armanasq.github.io/phd_tracker/")
        self.assertEqual(api_root("Armanasq/phd_tracker"), "https://api.github.com/repos/Armanasq/phd_tracker")

    def test_fork_scopes_homepage_and_api_destination(self) -> None:
        with patch.dict(os.environ, {"PHD_ATLAS_SITE_URL": ""}):
            data = load_metadata(self.file, repository="Independent/atlas")
        self.assertEqual(data["homepage"], "https://independent.github.io/atlas/")
        self.assertEqual(api_root("Independent/atlas"), "https://api.github.com/repos/Independent/atlas")
        self.assertEqual(data["topics"], ["phd-tracker", "github-pages"])

    def test_invalid_canonical_metadata_and_site_override_fail(self) -> None:
        with patch.dict(os.environ, {"PHD_ATLAS_SITE_URL": "http://unsafe.example/"}):
            with self.assertRaises(ValueError):
                load_metadata(self.file, repository="Independent/atlas")
        self.file.write_text(json.dumps({
            "repository": "Independent/atlas", "description": "Unexpected fork source",
            "homepage": "https://independent.github.io/atlas/", "topics": ["phd-tracker"],
        }), encoding="utf-8")
        with patch.dict(os.environ, {"PHD_ATLAS_SITE_URL": ""}):
            with self.assertRaises(ValueError):
                load_metadata(self.file, repository="Armanasq/phd_tracker")

    def test_fork_can_define_its_own_versioned_about_metadata(self) -> None:
        self.file.write_text(json.dumps({
            "repository": "Independent/atlas",
            "description": "Independent self-hostable PhD evidence workspace",
            "homepage": "https://independent.github.io/atlas/",
            "topics": ["independent", "research-applications"],
        }), encoding="utf-8")
        with patch.dict(os.environ, {"PHD_ATLAS_SITE_URL": ""}):
            values = load_metadata(self.file, repository="Independent/atlas")
        self.assertEqual(values["description"], "Independent self-hostable PhD evidence workspace")
        self.assertEqual(values["topics"], ["independent", "research-applications"])
        self.assertEqual(values["homepage"], "https://independent.github.io/atlas/")
        with self.assertRaises(ValueError):
            load_metadata(self.file, repository="Other/repository")

    def test_fork_update_uses_only_explicit_repository(self) -> None:
        settings = load_metadata(self.file, repository="Independent/atlas")
        requests: list = []

        class Response(io.BytesIO):
            status = 200

        def reply(request, timeout):
            requests.append(request)
            if request.method == "PATCH":
                return Response(b"{}")
            return Response(b'{"names":["phd-tracker","github-pages"]}')

        with patch("scripts.sync_repository_metadata.urlopen", side_effect=reply):
            write_metadata(settings, "synthetic-test-token", repository="Independent/atlas")
        self.assertEqual(len(requests), 2)
        self.assertTrue(all("Independent/atlas" in item.full_url for item in requests))
        self.assertFalse(any("Armanasq/phd_tracker" in item.full_url for item in requests))
        self.assertEqual(requests[0].get_method(), "PATCH")
        self.assertEqual(requests[1].get_method(), "PUT")

    def test_read_only_verification_does_not_write(self) -> None:
        settings = load_metadata(self.file, repository="Independent/atlas")
        requests: list = []

        class Response(io.BytesIO):
            status = 200

        def reply(request, timeout):
            requests.append(request)
            if request.full_url.endswith("/topics"):
                return Response(b'{"names":["phd-tracker","github-pages"]}')
            return Response(json.dumps(settings).encode())

        with patch("scripts.sync_repository_metadata.urlopen", side_effect=reply):
            verify_metadata(settings, repository="Independent/atlas")
        self.assertEqual([item.get_method() for item in requests], ["GET", "GET"])
        self.assertTrue(all("Authorization" not in item.headers for item in requests))


if __name__ == "__main__":
    unittest.main()
