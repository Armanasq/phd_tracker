from __future__ import annotations

import hashlib
import unittest

from scripts.verify_pages_release import validate_pages_url, verify_published_files

COMMIT = "a" * 40


class RemoteReleaseVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = {
            "index.html": b"<!doctype html><html></html>",
            "app.js": b"export const app = true;",
            "modules/source-claims.mjs": b"export const evidence = true;",
        }
        self.manifest = {
            "schema_version": 1,
            "commit": COMMIT,
            "asset_count": len(self.files),
            "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()},
        }

    def test_all_assets_and_versions_are_checked(self) -> None:
        report = verify_published_files(self.manifest, self.files.__getitem__, COMMIT)
        self.assertEqual(report["verified_assets"], 3)
        self.assertEqual(report["verified_bytes"], sum(map(len, self.files.values())))
        with self.assertRaises(ValueError):
            verify_published_files(self.manifest, self.files.__getitem__, "b" * 40)
        self.files["modules/source-claims.mjs"] = b"export const evidence = false;"
        with self.assertRaisesRegex(ValueError, "source-claims.mjs"):
            verify_published_files(self.manifest, self.files.__getitem__, COMMIT)

    def test_missing_or_unlisted_assets_are_not_silently_accepted(self) -> None:
        with self.assertRaises(KeyError):
            verify_published_files(self.manifest, lambda path: {"index.html": b"html"}[path], COMMIT)
        self.manifest["sha256"]["unexpected.mjs"] = "b" * 64
        with self.assertRaises(ValueError):
            verify_published_files(self.manifest, self.files.__getitem__, COMMIT)

    def test_manifest_path_and_sha_validation(self) -> None:
        for path in ("../config.env", "/absolute.html", "nested//file.js", "data?x=1"):
            with self.subTest(path=path):
                invalid = {**self.manifest, "sha256": {**self.manifest["sha256"], path: "b" * 64},
                           "asset_count": self.manifest["asset_count"] + 1}
                with self.assertRaises(ValueError):
                    verify_published_files(invalid, self.files.__getitem__, COMMIT)
        with self.assertRaises(ValueError):
            verify_published_files({**self.manifest, "commit": "b" * 40},
                                   self.files.__getitem__, COMMIT)

    def test_url_validation_requires_public_https(self) -> None:
        self.assertEqual(validate_pages_url("https://armanasq.github.io/phd_tracker/"),
                         "https://armanasq.github.io/phd_tracker")
        for address in ("http://example.org", "https://localhost/app",
                        "https://127.0.0.1", "https://user:token@example.org",
                        "https://example.org/?secret=1", "https://example.org:8443/app"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                validate_pages_url(address)


if __name__ == "__main__":
    unittest.main()
